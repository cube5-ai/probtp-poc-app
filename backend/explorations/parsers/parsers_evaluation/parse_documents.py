"""
Parse the documents in the input directory and write the results to the output directory
"""
# %%
import json
from pathlib import Path

from parsing_pipelines import extend_solo, pymupdf4llm_solo, mistral_ocr_solo

parsing_pipelines = {
    #"extend_solo": extend_solo,
    #"pymupdf4llm_solo": pymupdf4llm_solo,
    "mistral_ocr_solo": mistral_ocr_solo, 
}

# list documents in the input directory
input_dir = Path("documents")
documents = list(input_dir.glob("*.pdf"))

output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)

# print the number of documents
print(f"Found {len(documents)} documents")
print(documents)

# %%
# parse the documents
for parser_name, parser in parsing_pipelines.items():
    print(f"Parsing with {parser_name}")
    for document in documents[:1]:
        data = parser.parse_document(str(document.absolute()))
        output_dir_parser = output_dir / parser_name
        output_dir_parser.mkdir(parents=True, exist_ok=True)

        output_json_file = output_dir_parser / document.name.replace(".pdf", ".json")
        with open(output_json_file, "w") as f:
            json.dump(data, f)

        output_md_file = output_dir_parser / document.name.replace(".pdf", ".md")
        parser.write_to_markdown(data, str(output_md_file.absolute()))


# %%