import os
from pathlib import Path

import pymupdf4llm  # type: ignore
from anthropic import Anthropic, AnthropicVertex
from dotenv import load_dotenv
from llama_cloud_services import LlamaParse  # type: ignore

from .pymupdf_lock import pymupdf_lock

load_dotenv()

# Extract parser name from current file
PARSER_NAME = Path(__file__).stem

LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "")
ANTHROPIC_PROVIDER = "direct"  # "vertex" or "direct"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REGION = "global"
PROJECT_ID = os.getenv("PROJECT_ID", "probtp-poc-prod")


def parse_with_llamaparse(file_path: str) -> dict[int, str]:
    """
    Parse document with LlamaParse and return pages indexed by page number.
    """
    parser = LlamaParse(
        api_key=LLAMAPARSE_API_KEY,
        parse_mode="parse_page_with_llm",
        high_res_ocr=True,
        adaptive_long_table=True,
        outlined_table_extraction=True,
        output_tables_as_HTML=False,  # Keep as markdown for consistency
    )

    # Parse document
    result = parser.parse(file_path)

    # Extract markdown by page
    markdown_documents = result.get_markdown_documents(split_by_page=True)

    # Map pages by page number
    pages_by_num: dict[int, str] = {}
    for idx, doc in enumerate(markdown_documents):
        page_num = idx + 1  # 1-indexed
        pages_by_num[page_num] = doc.text

    return pages_by_num


def extract_pymupdf_pages(file_path: str) -> list[str]:
    """
    Return list of per-page markdown strings from PyMuPDF4LLM.
    Thread-safe: uses shared global lock to prevent concurrent calls to pymupdf4llm.
    """
    with pymupdf_lock:
        result = pymupdf4llm.to_markdown(
            file_path,
            page_chunks=True,
            write_images=False,
            image_size_limit=0,
            table_strategy="lines_strict",
        )

    pages: list[str] = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                pages.append(item.get("text", ""))
            else:
                pages.append(str(item))
    else:
        pages.append(str(result))
    return pages


def build_repair_prompt(llamaparse_page_md: str, pymupdf_page_md: str) -> str:
    """
    Compose repair prompt for a single page combining LlamaParse and PyMuPDF content.
    """
    return (
        "You are a document reconstruction expert. Your task is to REPAIR the OCR-parsed page,\n"
        "with a focus on TABLES, producing clean, unambiguous (no implicit merged cells) LLM-readable Markdown that is\n"
        "as close to the original layout as possible.\n\n"
        "Inputs:\n"
        "- llamaparse_page: Higher-level structured markdown from LlamaParse with better layout.\n"
        "- pymupdf_page: Deterministic text extraction with exact wording but poor layout.\n\n"
        "Strict rules:\n"
        "- Use exact wording from pymupdf_page when there is any discrepancy.\n"
        "- Use layout cues from llamaparse_page to reconstruct headings, lists, and TABLES.\n"
        "- For tables:\n"
        "   - ensure clear headers, for unnamed columns, add the column number as header\n"
        "   - consistent columns\n"
        "   - avoid empty cells, replicate the value of merged cells in all cells of the merged range, put a '-' in empty cells for non merged cells\n"
        "   - avoid ambiguity.\n"
        "- Prefer GitHub-flavored Markdown tables; do not add content not in inputs.\n"
        "- Never hallucinate or invent data. Do not include page numbers or separators.\n"
        "- Keep content only for THIS page.\n\n"
        "Return ONLY the final repaired Markdown for this page.\n\n\n"
        "<llamaparse_page>\n" + llamaparse_page_md + "\n</llamaparse_page>\n\n\n"
        "<pymupdf_page>\n" + pymupdf_page_md + "\n</pymupdf_page>\n"
    )


def parse_document(file_path: str):
    """
    Parse with LlamaParse, then repair per page with Claude Sonnet 4.5 using PyMuPDF for exact wording.
    """
    # Parse with LlamaParse
    try:
        llamaparse_pages = parse_with_llamaparse(file_path)
    except Exception as e:
        return {
            "chunks": [],
            "metadata": {
                "source": file_path,
                "parser": PARSER_NAME,
                "error": f"Failed to parse with LlamaParse: {e}",
            },
        }

    # Extract PyMuPDF pages
    pymupdf_pages = extract_pymupdf_pages(file_path)

    # Select client and model based on provider
    client: Anthropic | AnthropicVertex
    if ANTHROPIC_PROVIDER == "direct":
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        model = "claude-sonnet-4-5"
    else:
        client = AnthropicVertex(region=REGION, project_id=PROJECT_ID)
        model = "claude-sonnet-4-5@20250929"

    # Repair pages with Claude Sonnet 4.5
    repaired_chunks: list[dict] = []
    total_pages = max(len(pymupdf_pages), max(llamaparse_pages.keys()) if llamaparse_pages else 0)

    for page_index in range(1, total_pages + 1):
        llamaparse_md = llamaparse_pages.get(page_index, "")
        pymupdf_md = pymupdf_pages[page_index - 1] if page_index - 1 < len(pymupdf_pages) else ""

        prompt = build_repair_prompt(llamaparse_md, pymupdf_md)
        improved_markdown = llamaparse_md or pymupdf_md

        try:
            # Use streaming to handle long-running requests
            with client.messages.stream(
                model=model,
                max_tokens=32_000,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                # Collect the full response from stream
                full_text = ""
                for text in stream.text_stream:
                    full_text += text

                improved_markdown = full_text.strip() or improved_markdown
        except Exception as e:
            improved_markdown = llamaparse_md or pymupdf_md
            print(f"For file {file_path}, Error repairing page {page_index}: {e}")

        repaired_chunks.append(
            {
                "type": "page",
                "content": improved_markdown,
                "metadata": {"pageRange": {"start": page_index}},
            }
        )

    return {
        "chunks": repaired_chunks,
        "metadata": {
            "source": file_path,
            "parser": PARSER_NAME,
            "llm_model": "claude-sonnet-4.5",
        },
    }


def write_to_markdown(response: dict, file_path):
    """
    Flatten the repaired per-page chunks and write them to a Markdown file.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        for chunk in response.get("chunks", []):
            if chunk.get("type") == "page":
                page_num = chunk.get("metadata", {}).get("pageRange", {}).get("start", 1)
                f.write(f"---\n*Page {page_num}*\n---\n\n")
            content = chunk.get("content", "")
            if content:
                f.write(content)
                if not content.endswith("\n\n"):
                    f.write("\n\n")
