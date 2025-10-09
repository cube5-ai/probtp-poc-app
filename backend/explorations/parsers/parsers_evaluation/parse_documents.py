"""
Parse the documents in the input directory and write the results to the output directory
"""

# %%
import json
from pathlib import Path

from parsing_pipelines import (
    extend_llm_postprocessing_pymupdf_claude_sonnet_4_5,
    extend_llm_postprocessing_pymupdf_gemini_flash,
    extend_llm_postprocessing_pymupdf_gemini_pro,
    extend_solo,
    landing_ai_solo,
    landing_ai_xtd,
    # llamaparse_llm_postprocessing_pymupdf_claude_sonnet_4_5,
    mistral_ocr_solo,
    pulse_solo,
    pymupdf4llm_solo,
)

parsing_pipelines = {
    "extend_solo": extend_solo,
    "pulse_solo": pulse_solo,
    "pymupdf4llm_solo": pymupdf4llm_solo,
    "mistral_ocr_solo": mistral_ocr_solo,
    # #"extend_llm_postprocessing_pymupdf_gemini_pro": extend_llm_postprocessing_pymupdf_gemini_pro,
    "extend_llm_postprocessing_pymupdf_gemini_flash": extend_llm_postprocessing_pymupdf_gemini_flash,
    "extend_llm_postprocessing_pymupdf_claude_sonnet_4_5": extend_llm_postprocessing_pymupdf_claude_sonnet_4_5,
    "landing_ai_solo": landing_ai_solo,
    "landing_ai_xtd": landing_ai_xtd,  # Enhanced 5-phase pipeline
    #"llamaparse_llm_postprocessing_pymupdf_claude_sonnet_4_5": llamaparse_llm_postprocessing_pymupdf_claude_sonnet_4_5,
}

# List documents in the input directory
input_dir = Path("documents")
documents = list(input_dir.glob("*.pdf"))

output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)

# Print the number of documents
print(f"Found {len(documents)} documents")
print(documents)


# Helper function to check if document has already been processed
def is_document_processed(document_name: str, output_dir_parser: Path) -> bool:
    """Check if document has already been processed in parser output"""
    eval_file = output_dir_parser / f"{document_name.replace('.pdf', '.md')}"
    return eval_file.exists()


# Process a single document with a single parser
def process_document(parser_name: str, parser, document: Path) -> None:
    """Process a single document with a single parser"""
    output_dir_parser = output_dir / parser_name
    output_dir_parser.mkdir(parents=True, exist_ok=True)

    # Check if already processed
    if is_document_processed(document.name, output_dir_parser):
        print(f"[{parser_name}] Skipping {document.name} - already processed.")
        return

    print(f"[{parser_name}] Processing {document.name}")

    # Run parser
    data = parser.parse_document(str(document.absolute()))

    # Save JSON
    output_json_file = output_dir_parser / document.name.replace(".pdf", ".json")
    try:
        with open(output_json_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[{parser_name}] Error saving JSON: {e}")

    # Save markdown
    output_md_file = output_dir_parser / document.name.replace(".pdf", ".md")
    parser.write_to_markdown(data, str(output_md_file.absolute()))

    print(f"[{parser_name}] ✅ Completed {document.name}")


# Process all documents with a single parser
def process_parser(parser_name: str, parser, documents: list[Path]) -> None:
    """Process all documents with a single parser"""
    print(f"\n{'='*60}")
    print(f"Starting parser: {parser_name}")
    print(f"{'='*60}")

    # Process all documents for this parser sequentially
    for doc in documents:
        process_document(parser_name, parser, doc)

    print(f"[{parser_name}] All documents completed")


# Main function
def main():
    """Main function to orchestrate sequential parsing"""
    # Process all parsers sequentially
    for parser_name, parser in parsing_pipelines.items():
        process_parser(parser_name, parser, documents)

    print("\n" + "="*60)
    print("🎉 All parsing complete!")
    print("="*60)


# %%
# Run the main function
if __name__ == "__main__":
    main()
