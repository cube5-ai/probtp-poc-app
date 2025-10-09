"""
Read the data from the markdown files, in the output directory, infer the pipeline used to parse the document
"""
#%%
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig
from langfuse import Langfuse, observe
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from pydantic import BaseModel, Field

load_dotenv()


langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


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


class GeminiClientManager:
    """Context manager for proper Gemini client lifecycle management"""

    def __init__(self, use_vertex: bool = True):
        self.client = None
        self.use_vertex = use_vertex

    def __enter__(self):
        GoogleGenAIInstrumentor().instrument()

        if self.use_vertex:
            self.client = genai.Client(
                vertexai=True,
                project="probtp-poc-prod",
                location="global",
            )
        else:
            self.client = genai.Client(
                vertexai=False,
                api_key=os.getenv("GEMINI_API_KEY"),
            )
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            # Properly close the client if it has a close method
            if hasattr(self.client, "close"):
                try:
                    self.client.close()
                except Exception as e:
                    print(f"Error closing Gemini client: {e}")
            self.client = None


class AsyncGeminiClientManager:
    """Async context manager for proper Gemini client lifecycle management"""

    def __init__(self, use_vertex: bool = True):
        self.client = None
        self.use_vertex = use_vertex

    async def __aenter__(self):
        GoogleGenAIInstrumentor().instrument()

        if self.use_vertex:
            self.client = genai.Client(
                vertexai=True,
                project="probtp-poc-prod",
                location="global",
            )
        else:
            self.client = genai.Client(
                vertexai=False,
                api_key=os.getenv("GEMINI_API_KEY"),
            )
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            # Properly close the client if it has a close method
            if hasattr(self.client, "close"):
                try:
                    if asyncio.iscoroutinefunction(self.client.close):
                        await self.client.close()
                    else:
                        self.client.close()
                except Exception as e:
                    print(f"Error closing async Gemini client: {e}")
            self.client = None



def read_eval_data(file: Path) -> list[dict]:
    """
    Read the evaluation data from the json file
    """
    with open(file, encoding="utf-8") as f:
        eval_data = json.load(f)
    return eval_data



def generate_question_answer(eval_data: list[dict], file_name_in_qa: str) -> list[dict]:
    """
    Generate question/answer pairs from the evaluation data
    """
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



def evaluate_pipeline(file_qa_list: list[dict], data: str, pipeline_name: str, file_name: str = "", use_vertex: bool = False) -> list[dict[str, Any]]:
    """
    Evaluate the pipeline by asking for answers then grading them with structured output.
    """

    prompt_answer = (
        """
    You are an AI analyst expert in information extraction and lookup from a markdown document.
    Read the document and answer the question strictly based on it.



    <document>
    {document}
    </document>





    <question>
    {question}
    </question>


    Reminder:
        You are an AI analyst expert in information extraction and lookup from a markdown document.
        Read the document and answer the question strictly based on it.

    Provide a concise (on average 1 to 20 words, 60 words max), direct answer with no preamble:
    """
    )

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

    results: list[dict[str, Any]] = []
    with GeminiClientManager(use_vertex=use_vertex) as client:
        for qa in file_qa_list:
            answer_prompt = prompt_answer.format(document=data, question=qa["question"])
            answer_resp = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=answer_prompt,
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(thinking_budget=300)
                ),
            )
            candidate_answer = getattr(answer_resp, "text", "").strip()

            eval_prompt = (
                f"{prompt_evaluation}\n\n\n"
                f"<question>\n{qa['question']}\n</question>\n\n"
                f"<ground_truth>\n{qa['answer']}\n</ground_truth>\n\n"
                f"<candidate_answer>\n{candidate_answer}\n</candidate_answer>\n"
            )
            eval_resp = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=eval_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": EvaluationResult.model_json_schema(),
                },
                )
            raw_json = getattr(eval_resp, "text", "").strip()
            try:
                result = parse_evaluation_result(raw_json)
                result_as_dict = result.model_dump()
                result_as_dict["llm_answer"] = candidate_answer
                result_as_dict["ground_truth"] = qa["answer"]
                result_as_dict["question"] = qa["question"]
                result_as_dict["pipeline_name"] = pipeline_name
                result_as_dict["file_name"] = file_name
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
                    result_as_dict["file_name"] = file_name
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
                    result_as_dict["file_name"] = file_name
            results.append(result_as_dict)

    return results


async def evaluate_single_qa(client, qa: dict, data: str, pipeline_name: str, prompt_answer: str, prompt_evaluation: str, file_name: str = "") -> dict[str, Any]:
    """
    Evaluate a single Q&A pair asynchronously.
    """
    answer_prompt = prompt_answer.format(document=data, question=qa["question"])
    answer_resp = await client.aio.models.generate_content(
        model="gemini-2.5-pro",#-preview-09-2025",
        contents=answer_prompt,
        config=GenerateContentConfig(
            thinking_config=ThinkingConfig(thinking_budget=300),
            max_output_tokens=600,
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
        model="gemini-2.5-pro",#flash-preview-09-2025",
        contents=eval_prompt,
        config=GenerateContentConfig(
            response_mime_type= "application/json",
            thinking_config=ThinkingConfig(thinking_budget=300),
            response_schema= EvaluationResult.model_json_schema(),
            max_output_tokens=2000,
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
        result_as_dict["file_name"] = file_name
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
            result_as_dict["file_name"] = file_name
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
            result_as_dict["file_name"] = file_name

    return result_as_dict


async def evaluate_pipeline_async(file_qa_list: list[dict], data: str, pipeline_name: str, file_name: str = "", use_vertex: bool = False) -> list[dict[str, Any]]:
    """
    Async version of evaluate_pipeline using the Google Gen AI async client with parallel execution.
    """

    prompt_answer = (
        """
    You are an AI analyst expert in information extraction and lookup from a markdown document.
    Read the document and answer the question strictly based on it.



    <document>
    {document}
    </document>




    <question>
    {question}
    </question>


    Reminder:
        You are an AI analyst expert in information extraction and lookup from a markdown document.
        Read the document and answer the question strictly based on it.

    Provide a concise (on average 1 to 20 words, 60 words max), direct answer with no preamble:
    """
    )

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

    async with AsyncGeminiClientManager(use_vertex=use_vertex) as client:
        # Process tasks in batches of 5 to avoid rate limiting
        batch_size = 5
        all_results = []

        for i in range(0, len(file_qa_list), batch_size):
            batch = file_qa_list[i:i + batch_size]
            tasks = [
                evaluate_single_qa(client, qa, data, pipeline_name, prompt_answer, prompt_evaluation, file_name)
                for qa in batch
            ]

            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks)
            print(f"Batch {i//batch_size + 1} of {len(file_qa_list)//batch_size} done", end='\r')
            all_results.extend(batch_results)

            # Add 1s pause between batches (except after the last batch)
            if i + batch_size < len(file_qa_list):
                await asyncio.sleep(1)

    return all_results


def write_results_to_json(enriched_results: list[dict[str, Any]], pipeline_name: str):
    """
    Write the results to a json file in output/evals/pipeline_name.json
    """
    with open(Path("output/evals") / f"{pipeline_name}.json", "w", encoding="utf-8") as f:
        json.dump(enriched_results, f, indent=2, ensure_ascii=False)


def quick_performance_results(results: list[dict[str, Any]]):
    """
    Quick summarize the results
    """
    return {
        "correct": sum(1 for r in results if r["verdict"] == "CORRECT")/len(results),
        "partial": sum(1 for r in results if r["verdict"] == "PARTIAL")/len(results),
        "hallucination": sum(1 for r in results if r["verdict"] == "HALLUCINATION")/len(results),
        "missed": sum(1 for r in results if r["verdict"] == "MISSED")/len(results),
    }

# %%

# Global configuration
qa_file_file_name_map = {
    "#1": ["File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.md", ],
    "#2": [
        "File #2 - Laurent M - tableau garantie fm 2025 word.md",
        "File #3 - Panorama FMC 2025.md"
    ],
}
# reverse the file_name_map
file_name_file_qa_map = {filename: k for k, filenames in qa_file_file_name_map.items() for filename in filenames}


async def main():
    """
    Main async function to process all pipelines and evaluate them.
    """
    output_dir = Path("output")
    evals_dir = Path("output/evals")

    # Get the eval data
    eval_data = read_eval_data(Path("eval_data/data_0.json"))

    # Iterate over subdirectories in output_dir and process markdown files for each pipeline

    for pipeline_dir in output_dir.iterdir():
        if not pipeline_dir.is_dir() or pipeline_dir.name == "evals":
            continue
        pipeline_name = pipeline_dir.name

        # Check if pipeline folder has any markdown files
        md_files = [f for f in pipeline_dir.iterdir() if f.is_file() and f.name.endswith(".md")]
        if not md_files:
            print(f"Skipping {pipeline_name} - no markdown files found")
            continue

        # Check if evaluation JSON already exists
        eval_json_path = evals_dir / f"{pipeline_name}.json"
        if eval_json_path.exists():
            print(f"Skipping {pipeline_name} - evaluation already exists at {eval_json_path}")
            continue

        all_results = []
        for file_path in pipeline_dir.iterdir():
            if file_path.is_file() and file_path.name.endswith(".md"):
                file_name = file_path.name
                qa_list = generate_question_answer(eval_data, file_name_file_qa_map[file_name])
                print("Extracted question/answer pairs", len(qa_list))
                # Use the async version (use_vertex=False to use Gemini API)
                results = await evaluate_pipeline_async(qa_list, file_path.read_text(encoding="utf-8"), pipeline_name, file_name, use_vertex=False)
                print(f"Results for {pipeline_name}, {file_name}: {len(results)}")
                print(json.dumps(quick_performance_results(results), indent=2))
                all_results.extend(results)

        write_results_to_json(all_results, pipeline_name)
        print(f"Results for {pipeline_name}")
        print(json.dumps(quick_performance_results(all_results), indent=2))


def main_sync():
    """
    Synchronous main function for backward compatibility.
    """
    output_dir = Path("output")
    evals_dir = Path("output/evals")

    # Get the eval data
    eval_data = read_eval_data(Path("eval_data/data_0.json"))

    # Iterate over subdirectories in output_dir and process markdown files for each pipeline
    for pipeline_dir in output_dir.iterdir():
        if not pipeline_dir.is_dir() or pipeline_dir.name == "evals":
            continue
        pipeline_name = pipeline_dir.name

        # Check if pipeline folder has any markdown files
        md_files = [f for f in pipeline_dir.iterdir() if f.is_file() and f.name.endswith(".md")]
        if not md_files:
            print(f"Skipping {pipeline_name} - no markdown files found")
            continue

        # Check if evaluation JSON already exists
        eval_json_path = evals_dir / f"{pipeline_name}.json"
        if eval_json_path.exists():
            print(f"Skipping {pipeline_name} - evaluation already exists at {eval_json_path}")
            continue

        all_results = []
        for file_path in pipeline_dir.iterdir():
            if file_path.is_file() and file_path.name.endswith(".md"):
                file_name = file_path.name
                qa_list = generate_question_answer(eval_data, file_name_file_qa_map[file_name])
                print("Extracted question/answer pairs", len(qa_list))
                # Use the sync version with fixed parameters (use_vertex=False to use Gemini API)
                results = evaluate_pipeline(qa_list, file_path.read_text(encoding="utf-8"), pipeline_name, file_name, use_vertex=False)
                print(f"Results for {pipeline_name}, {file_name}: {len(results)}")
                print(json.dumps(quick_performance_results(results), indent=2))
                all_results.extend(results)

        write_results_to_json(all_results, pipeline_name)
        print(f"Results for {pipeline_name}")
        print(json.dumps(quick_performance_results(all_results), indent=2))


# Run the async version by default
if __name__ == "__main__":
    asyncio.run(main())

# %%
