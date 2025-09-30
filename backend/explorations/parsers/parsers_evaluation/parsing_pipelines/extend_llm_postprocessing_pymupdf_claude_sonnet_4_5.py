
import os
from pathlib import Path

import pymupdf4llm  # type: ignore
import requests
from anthropic import AnthropicVertex
from dotenv import load_dotenv

from .pymupdf_lock import pymupdf_lock

load_dotenv()

# Extract parser name from current file
PARSER_NAME = Path(__file__).stem

EXTEND_API_KEY = os.getenv("EXTEND_API_KEY", "NO API KEY")
REGION = os.getenv("REGION", "global")
PROJECT_ID = os.getenv("PROJECT_ID", "probtp-poc-prod")


def upload_file(file_path: str):
    """
    Upload a file to the Extend API
    """

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(
                "https://api.extend.ai/files/upload",
                files=files,
                headers={
                    "Authorization": f"Bearer {EXTEND_API_KEY}",
                    "x-extend-api-version": "2025-04-21",
                }
            )
        return response.json()


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


def build_repair_prompt(extend_page_md: str, pymupdf_page_md: str) -> str:
    """
    Compose repair prompt for a single page combining Extend OCR and PyMuPDF content.
    """

    return (
        "You are a document reconstruction expert. Your task is to REPAIR the OCR-parsed page,\n"
        "with a focus on TABLES, producing clean, unambiguous, human-readable Markdown that is\n"
        "as close to the original layout as possible.\n\n"
        "Inputs:\n"
        "- extend_page: Higher-level structured markdown from a VLLM OCR with better layout.\n"
        "- pymupdf_page: Deterministic text extraction with exact wording but poor layout.\n\n"
        "Strict rules:\n"
        "- Use exact wording from pymupdf_page when there is any discrepancy.\n"
        "- Use layout cues from extend_page to reconstruct headings, lists, and TABLES.\n"
        "- For tables: ensure clear headers, consistent columns, and avoid ambiguity.\n"
        "  Prefer GitHub-flavored Markdown tables; do not add content not in inputs.\n"
        "- Never hallucinate or invent data. Do not include page numbers or separators.\n"
        "- Keep content only for THIS page.\n\n"
        "Return ONLY the final repaired Markdown for this page.\n\n\n"
        "<extend_page>\n" + extend_page_md + "\n</extend_page>\n\n\n"
        "<pymupdf_page>\n" + pymupdf_page_md + "\n</pymupdf_page>\n"
    )

def parse_document(file_path: str):
    """
    Parse with Extend, then repair per page with Claude Sonnet 4.5 using PyMuPDF for exact wording.
    """

    # Upload to Extend
    file_info = upload_file(file_path)
    file_id = file_info.get("file", {}).get("id")
    if not file_id:
        return {
            "chunks": [],
            "metadata": {
                "source": file_path,
                "parser": PARSER_NAME,
                "error": "Failed to upload to Extend",
            },
        }

    # Parse with Extend
    response = requests.post(
        "https://api.extend.ai/parse",
        json={
            "file": {"fileId": file_id},
            "config": {
                "target": "spatial",
                "blockOptions": {
                    "text": {"signatureDetectionEnabled": True},
                    "tables": {
                        "enabled": True,
                        "targetFormat": "markdown",
                        "tableHeaderContinuationEnabled": True,
                    },
                    "figures": {
                        "enabled": True,
                        "figureImageClippingEnabled": True,
                    },
                },
                "advancedOptions": {
                    "agenticOcrEnabled": True,
                    "pageRotationEnabled": True,
                },
                "chunkingStrategy": {"type": "page"},
            },
        },
        headers={
            "Authorization": f"Bearer {EXTEND_API_KEY}",
            "Content-Type": "application/json",
            "x-extend-api-version": "2025-04-21",
        },
    )

    extend_json = response.json() if hasattr(response, "json") else {}
    extend_chunks = extend_json.get("chunks", []) if isinstance(extend_json, dict) else []

    # Map Extend pages by page number
    extend_pages_by_num: dict[int, str] = {}
    for chunk in extend_chunks:
        if chunk.get("type") == "page":
            page_num = chunk.get("metadata", {}).get("pageRange", {}).get("start")
            if isinstance(page_num, int):
                extend_pages_by_num[page_num] = chunk.get("content", "")

    # Extract PyMuPDF pages
    pymupdf_pages = extract_pymupdf_pages(file_path)

    # Repair pages with Claude Sonnet 4.5
    client = AnthropicVertex(region=REGION, project_id=PROJECT_ID)

    repaired_chunks: list[dict] = []
    total_pages = max(len(pymupdf_pages), max(extend_pages_by_num.keys()) if extend_pages_by_num else 0)
    for page_index in range(1, total_pages + 1):
        extend_md = extend_pages_by_num.get(page_index, "")
        pymupdf_md = pymupdf_pages[page_index - 1] if page_index - 1 < len(pymupdf_pages) else ""

        prompt = build_repair_prompt(extend_md, pymupdf_md)
        improved_markdown = extend_md or pymupdf_md
        try:
            message = client.messages.create(
                model="claude-sonnet-4-5@20250929",
                max_tokens=32_000,
                messages=[{"role": "user", "content": prompt}],
            )
            if message.content and hasattr(message.content[0], "text"):
                improved_markdown = message.content[0].text.strip() or improved_markdown
        except Exception:
            improved_markdown = extend_md or pymupdf_md

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
