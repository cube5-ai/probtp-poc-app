"""
VQA pipeline using Gemini flash latest 2.5 to evaluate documents from PDF images.
Converts PDFs to images, uploads them to Gemini, and evaluates Q&A performance.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Literal

import fitz  # PyMuPDF  # type: ignore
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, Part, ThinkingConfig
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from pydantic import BaseModel, Field

load_dotenv()


class EvaluationResult(BaseModel):
    """Structured evaluation result returned by the LLM."""

    explanation: str
    verdict: Literal["CORRECT", "PARTIAL", "HALLUCINATION", "MISSED"]
    missing_information: list[str] = []
    evidence_quotes: list[str] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def parse_evaluation_result(raw_json: str) -> "EvaluationResult":
    """Parse and validate a JSON string into an EvaluationResult model."""
    return EvaluationResult.model_validate_json(raw_json)


class AsyncGeminiClientManager:
    """Async context manager for proper Gemini client lifecycle management"""

    def __init__(self):
        self.client = None

    async def __aenter__(self):
        GoogleGenAIInstrumentor().instrument()

        self.client = genai.Client(
            vertexai=True,
            project="probtp-poc-prod",
            location="global",
        )
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            if hasattr(self.client, "close"):
                try:
                    if asyncio.iscoroutinefunction(self.client.close):
                        await self.client.close()
                    else:
                        self.client.close()
                except Exception as e:
                    print(f"Error closing async Gemini client: {e}")
            self.client = None


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 300) -> list[Path]:
    """
    Convert PDF pages to images at specified DPI using PyMuPDF.
    Returns list of image paths.
    """
    doc = fitz.open(pdf_path)
    file_name = pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Use dpi parameter directly instead of calculating matrix
        pix = page.get_pixmap(dpi=dpi)

        # Save as PNG
        image_path = output_dir / f"{file_name}_page_{page_num + 1}.png"
        pix.save(str(image_path))
        image_paths.append(image_path)

    doc.close()
    return image_paths


def load_images_as_parts(image_paths: list[Path]) -> list[Part]:
    """Load images as Part objects from bytes for Vertex AI."""
    image_parts = []

    for image_path in image_paths:
        print(f"Loading {image_path.name}...", end="\r")
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        # Create Part from bytes with appropriate mime type
        image_part = Part.from_bytes(data=image_bytes, mime_type="image/png")
        image_parts.append(image_part)

    print(f"Loaded {len(image_parts)} images successfully     ")
    return image_parts


def read_eval_data(file: Path) -> list[dict]:
    """Read the evaluation data from the json file."""
    with open(file, encoding="utf-8") as f:
        eval_data = json.load(f)
    return eval_data


def generate_question_answer(eval_data: list[dict], file_name_in_qa: str) -> list[dict]:
    """Generate question/answer pairs from the evaluation data."""
    qa_list = []
    for eval_obj in eval_data:
        if eval_obj['Fichier'] != file_name_in_qa:
            continue
        question = "Quel est la prise en charge ou le remboursement pour"
        question += f" {eval_obj['Catégorie 1']} > {eval_obj['Catégorie 2']}"
        question += f" > {eval_obj['Catégorie 3']}" if eval_obj.get('Catégorie 3') else ""
        question += f" au niveau de garantie {eval_obj['Niveau']} ?"

        if eval_obj['Valeur'] == "Non pris en charge":
            answer = "Non pris en charge"
        elif eval_obj['Valeur'] is None:
            answer = "L'information sur le remboursement n'est pas disponible"
        else:
            answer = f"Le remboursement est de {eval_obj['Valeur']}"
            if eval_obj.get('Conditions'):
                answer += f" avec les conditions suivantes: {eval_obj['Conditions']}"
            answer += "."
        qa_list.append({
            "id": eval_obj["id"],
            "file_name": eval_obj['Fichier'],
            "question": question,
            "answer": answer,
        })
    return qa_list


async def evaluate_single_qa_vqa(
    client: genai.Client,
    qa: dict,
    image_parts: list[Part],
    pipeline_name: str,
    prompt_answer: str,
    prompt_evaluation: str
) -> dict[str, Any]:
    """Evaluate a single Q&A pair using VQA with image parts."""

    # Create content with images and question
    answer_content: list[Any] = [prompt_answer.format(question=qa["question"])]
    answer_content.extend(image_parts)

    answer_resp = await client.aio.models.generate_content(
        model="gemini-2.5-flash-preview-09-2025",
        contents=answer_content,
        config=GenerateContentConfig(
            thinking_config=ThinkingConfig(thinking_budget=500),
            max_output_tokens=1000,
            temperature=0.
        ),
    )
    candidate_answer = getattr(answer_resp, "text", "").strip()

    eval_prompt = (
        f"{prompt_evaluation}\n\n\n"
        f"<question>\n{qa['question']}\n</question>\n\n"
        f"<ground_truth>\n{qa['answer']}\n</ground_truth>\n\n"
        f"<candidate_answer>\n{candidate_answer}\n</candidate_answer>\n"
    )

    eval_resp = await client.aio.models.generate_content(
        model="gemini-2.5-flash-preview-09-2025",
        contents=eval_prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=ThinkingConfig(thinking_budget=300),
            response_schema=EvaluationResult.model_json_schema(),
            max_output_tokens=3000,
            temperature=0.
        ),
    )
    raw_json = getattr(eval_resp, "text", "").strip()

    try:
        result = parse_evaluation_result(raw_json)
        result_as_dict = result.model_dump()
        result_as_dict["llm_answer"] = candidate_answer
        result_as_dict["ground_truth"] = qa["answer"]
        result_as_dict["question"] = qa["question"]
        result_as_dict["pipeline_name"] = pipeline_name
    except Exception:
        start = raw_json.find("{")
        end = raw_json.rfind("}")
        if start != -1 and end != -1 and end > start:
            result = EvaluationResult.model_validate_json(raw_json[start : end + 1])
            result_as_dict = result.model_dump()
            result_as_dict["llm_answer"] = candidate_answer
            result_as_dict["ground_truth"] = qa["answer"]
            result_as_dict["question"] = qa["question"]
            result_as_dict["pipeline_name"] = pipeline_name
        else:
            result = EvaluationResult(
                verdict="HALLUCINATION",
                explanation="LLM did not return valid JSON per schema.",
                missing_information=[],
                evidence_quotes=[],
                confidence=0.0,
            )
            result_as_dict = result.model_dump()
            result_as_dict["verdict"] = "FAILED_LLM_CALL"
            result_as_dict["llm_answer"] = candidate_answer
            result_as_dict["ground_truth"] = qa["answer"]
            result_as_dict["question"] = qa["question"]
            result_as_dict["pipeline_name"] = pipeline_name

    return result_as_dict


async def evaluate_pipeline_vqa(
    client: genai.Client,
    file_qa_list: list[dict],
    image_parts: list[Part],
    pipeline_name: str
) -> list[dict[str, Any]]:
    """Async VQA evaluation using image parts with parallel execution."""

    prompt_answer = """
    You are an AI analyst expert in information extraction from insurance documents.
    Read the document images provided and answer the question strictly based on them.

    <question>
    {question}
    </question>

    Reminder:
        You are an AI analyst expert in information extraction from insurance documents.
        Read the document images and answer the question strictly based on them.

    Provide a concise (on average 1 to 20 words, 60 words max), direct answer with no preamble:
    """

    prompt_evaluation = """
    You are an expert evaluator of information retrieval quality from a document.

    You will receive three inputs delimited by XML tags:
    <question>...</question>
    <ground_truth>...</ground_truth>
    <candidate_answer>...</candidate_answer>

    Decide a verdict using ONLY these strict definitions:
    - CORRECT: Candidate fully matches ground_truth with no material omissions or additions.
    - PARTIAL: Candidate is directionally right but misses required details present in ground_truth.
    - HALLUCINATION: Candidate introduces content not supported by ground_truth or contradicts it.
    - MISSED: Candidate states information is not available while ground_truth contains it.

    Return ONLY a JSON object on a single line that strictly conforms to this schema:
    {{
      "verdict": "CORRECT|PARTIAL|HALLUCINATION|MISSED",
      "explanation": "string",
      "missing_information": ["string"],
      "evidence_quotes": ["string"],
      "confidence": 0.0
    }}

    Constraints:
    - Output JSON only. No prose, no markdown, no code fences.
    - Keep evidence_quotes minimal and verbatim from the provided inputs, or [] if none.
    - Use confidence 1.0 for obvious cases; otherwise estimate between 0.0 and 1.0.
    """

    # Process tasks in batches of 5 to avoid rate limiting
    batch_size = 5
    all_results = []

    for i in range(0, len(file_qa_list), batch_size):
        batch = file_qa_list[i:i + batch_size]
        tasks = [
            evaluate_single_qa_vqa(
                client, qa, image_parts, pipeline_name, prompt_answer, prompt_evaluation
            )
            for qa in batch
        ]

        # Execute batch concurrently
        batch_results = await asyncio.gather(*tasks)
        print(f"Batch {i//batch_size + 1}/{(len(file_qa_list)-1)//batch_size + 1} done", end='\r')
        all_results.extend(batch_results)

        # Add 1s pause between batches (except after the last batch)
        if i + batch_size < len(file_qa_list):
            await asyncio.sleep(1)

    return all_results


def write_results_to_json(enriched_results: list[dict[str, Any]], pipeline_name: str, output_dir: Path):
    """Write the results to a json file in output/evals/pipeline_name.json"""
    evals_dir = output_dir / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)

    with open(evals_dir / f"{pipeline_name}.json", "w", encoding="utf-8") as f:
        json.dump(enriched_results, f, indent=2, ensure_ascii=False)


def quick_performance_results(results: list[dict[str, Any]]):
    """Quick summarize the results"""
    if not results:
        return {}
    return {
        "correct": sum(1 for r in results if r["verdict"] == "CORRECT")/len(results),
        "partial": sum(1 for r in results if r["verdict"] == "PARTIAL")/len(results),
        "hallucination": sum(1 for r in results if r["verdict"] == "HALLUCINATION")/len(results),
        "missed": sum(1 for r in results if r["verdict"] == "MISSED")/len(results),
    }


# File mapping from evaluate_pipelines.py
qa_file_file_name_map = {
    "#1": "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE",
    "#2": "File #2 - Laurent M - tableau garantie fm 2025 word",
}


async def main():
    """Main async function to process PDFs and evaluate them using VQA."""

    pipeline_name = "vqa_gemini_flash_latest"
    base_dir = Path(__file__).parent.parent
    documents_dir = base_dir / "documents"
    output_dir = base_dir / "output"
    vqa_output_dir = output_dir / "vqa" / pipeline_name
    evals_dir = output_dir / "evals"

    # Check if evaluation JSON already exists
    eval_json_path = evals_dir / f"{pipeline_name}.json"
    if eval_json_path.exists():
        print(f"Evaluation already exists at {eval_json_path}")
        return

    # Get the eval data
    eval_data = read_eval_data(base_dir / "eval_data" / "data_0.json")

    all_results = []

    async with AsyncGeminiClientManager() as client:
        # Process each PDF file
        for qa_file_key, base_name in qa_file_file_name_map.items():
            pdf_path = documents_dir / f"{base_name}.pdf"

            if not pdf_path.exists():
                print(f"PDF not found: {pdf_path}")
                continue

            print(f"\nProcessing {pdf_path.name}...")

            # Convert PDF to images
            print("Converting PDF to images...")
            image_paths = convert_pdf_to_images(pdf_path, vqa_output_dir, dpi=300)
            print(f"Created {len(image_paths)} images")

            # Load images as Part objects
            print("Loading images as Part objects...")
            image_parts = load_images_as_parts(image_paths)

            # Generate Q&A pairs for this file
            qa_list = generate_question_answer(eval_data, qa_file_key)
            print(f"Generated {len(qa_list)} Q&A pairs")

            # Evaluate using VQA
            print("Evaluating with Gemini flash latest VQA...")
            results = await evaluate_pipeline_vqa(client, qa_list, image_parts, pipeline_name)

            print(f"\nResults for {pdf_path.name}:")
            print(json.dumps(quick_performance_results(results), indent=2))

            all_results.extend(results)

    # Write all results
    write_results_to_json(all_results, pipeline_name, output_dir)
    print(f"\n\nOverall Results for {pipeline_name}:")
    print(json.dumps(quick_performance_results(all_results), indent=2))
    print(f"\nResults saved to {eval_json_path}")


if __name__ == "__main__":
    asyncio.run(main())
