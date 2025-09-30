"""
Parse the documents in the input directory and write the results to the output directory
"""

# %%
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from parsing_pipelines import (
    extend_llm_postprocessing_pymupdf_claude_sonnet_4_5,
    extend_llm_postprocessing_pymupdf_gemini_flash,
    extend_llm_postprocessing_pymupdf_gemini_pro,
    extend_solo,
    mistral_ocr_solo,
    pymupdf4llm_solo,
)

parsing_pipelines = {
    "extend_solo": extend_solo,
    "pymupdf4llm_solo": pymupdf4llm_solo,
    "mistral_ocr_solo": mistral_ocr_solo,
    #"extend_llm_postprocessing_pymupdf_gemini_pro": extend_llm_postprocessing_pymupdf_gemini_pro,
    "extend_llm_postprocessing_pymupdf_gemini_flash": extend_llm_postprocessing_pymupdf_gemini_flash,
    "extend_llm_postprocessing_pymupdf_claude_sonnet_4_5": extend_llm_postprocessing_pymupdf_claude_sonnet_4_5,
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
async def process_document(parser_name: str, parser, document: Path, executor: ThreadPoolExecutor) -> None:
    """Process a single document with a single parser asynchronously"""
    output_dir_parser = output_dir / parser_name
    output_dir_parser.mkdir(parents=True, exist_ok=True)
    
    # Check if already processed
    if is_document_processed(document.name, output_dir_parser):
        print(f"[{parser_name}] Skipping {document.name} - already processed.")
        return
    
    print(f"[{parser_name}] Processing {document.name}")
    
    # Run parser in thread pool (parsers use synchronous HTTP calls)
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, parser.parse_document, str(document.absolute()))
    
    # Save JSON
    output_json_file = output_dir_parser / document.name.replace(".pdf", ".json")
    await loop.run_in_executor(
        executor,
        lambda: json.dump(data, open(output_json_file, "w"))
    )
    
    # Save markdown
    output_md_file = output_dir_parser / document.name.replace(".pdf", ".md")
    await loop.run_in_executor(
        executor,
        parser.write_to_markdown,
        data,
        str(output_md_file.absolute())
    )
    
    print(f"[{parser_name}] ✅ Completed {document.name}")


# Process all documents with a single parser
async def process_parser(parser_name: str, parser, documents: list[Path], executor: ThreadPoolExecutor) -> None:
    """Process all documents with a single parser"""
    print(f"\n{'='*60}")
    print(f"Starting parser: {parser_name}")
    print(f"{'='*60}")
    
    # Process all documents for this parser in parallel
    tasks = [process_document(parser_name, parser, doc, executor) for doc in documents]
    await asyncio.gather(*tasks)
    
    print(f"[{parser_name}] All documents completed")


# Main async function
async def main():
    """Main function to orchestrate parallel parsing"""
    # Create thread pool executor for synchronous I/O operations
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Process all parsers in parallel (each parser processes all docs in parallel)
        tasks = [
            process_parser(parser_name, parser, documents, executor)
            for parser_name, parser in parsing_pipelines.items()
        ]
        await asyncio.gather(*tasks)
    
    print("\n" + "="*60)
    print("🎉 All parsing complete!")
    print("="*60)


# %%
# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
