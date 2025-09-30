"""
Utilities to load results and compute metrics and detailed dataframes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


# File name mappings from evaluate_pipelines.py
QA_FILE_FILE_NAME_MAP = {
    "#1": "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.md",
    "#2": "File #2 - Laurent M - tableau garantie fm 2025 word.md",
}


def load_evaluation_results(eval_dir: Path) -> list[dict[str, Any]]:
    """Load all evaluation results from JSON files in the eval directory."""
    all_results = []
    for json_file in eval_dir.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            results = json.load(f)
            all_results.extend(results)
    return all_results


def compute_global_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall performance metrics across all evaluations."""
    total = len(results)
    if total == 0:
        return {}

    verdict_counts = {
        "correct": sum(1 for r in results if r["verdict"] == "CORRECT"),
        "partial": sum(1 for r in results if r["verdict"] == "PARTIAL"),
        "hallucination": sum(1 for r in results if r["verdict"] == "HALLUCINATION"),
        "missed": sum(1 for r in results if r["verdict"] == "MISSED"),
    }

    avg_confidence = sum(r.get("confidence", 0.0) for r in results) / total

    return {
        "total_evaluations": total,
        "correct_count": verdict_counts["correct"],
        "partial_count": verdict_counts["partial"],
        "hallucination_count": verdict_counts["hallucination"],
        "missed_count": verdict_counts["missed"],
        "correct_rate": verdict_counts["correct"] / total,
        "partial_rate": verdict_counts["partial"] / total,
        "hallucination_rate": verdict_counts["hallucination"] / total,
        "missed_rate": verdict_counts["missed"] / total,
        "avg_confidence": avg_confidence,
        "success_rate": (verdict_counts["correct"] + verdict_counts["partial"]) / total,
    }


def compute_pipeline_metrics(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute performance metrics grouped by pipeline."""
    df = pd.DataFrame(results)

    pipeline_stats = df.groupby("pipeline_name").agg({
        "verdict": [
            ("total", "count"),
            ("correct", lambda x: (x == "CORRECT").sum()),
            ("partial", lambda x: (x == "PARTIAL").sum()),
            ("hallucination", lambda x: (x == "HALLUCINATION").sum()),
            ("missed", lambda x: (x == "MISSED").sum()),
        ],
        "confidence": "mean"
    }).round(4)

    pipeline_stats.columns = ["_".join(col).strip("_") for col in pipeline_stats.columns]

    pipeline_stats["correct_rate"] = (
        pipeline_stats["verdict_correct"] / pipeline_stats["verdict_total"]
    ).round(4)
    pipeline_stats["partial_rate"] = (
        pipeline_stats["verdict_partial"] / pipeline_stats["verdict_total"]
    ).round(4)
    pipeline_stats["hallucination_rate"] = (
        pipeline_stats["verdict_hallucination"] / pipeline_stats["verdict_total"]
    ).round(4)
    pipeline_stats["missed_rate"] = (
        pipeline_stats["verdict_missed"] / pipeline_stats["verdict_total"]
    ).round(4)
    pipeline_stats["success_rate"] = (
        (pipeline_stats["verdict_correct"] + pipeline_stats["verdict_partial"]) / pipeline_stats["verdict_total"]
    ).round(4)

    return pipeline_stats.reset_index()


def build_question_to_file_map(eval_data_path: Path) -> dict[str, dict[str, str]]:
    """Build mapping from generated question text to file identifiers from eval_data.

    Returns mapping: question -> {"file_id": "#1", "file_name": "Pretty.md"}
    """
    if not eval_data_path.exists():
        return {}

    with open(eval_data_path, encoding="utf-8") as f:
        eval_data = json.load(f)

    mapping: dict[str, dict[str, str]] = {}
    for obj in eval_data:
        # Rebuild question exactly as used during evaluation
        question = "Quel est la prise en charge ou le remboursement pour"
        question += f" {obj['Catégorie 1']} > {obj['Catégorie 2']}"
        question += f" > {obj['Catégorie 3']}" if obj.get('Catégorie 3') else ""
        question += f" au niveau de garantie {obj['Niveau']} ?"

        file_id = obj.get("Fichier", "")
        file_name = QA_FILE_FILE_NAME_MAP.get(file_id, file_id)
        mapping[question] = {"file_id": file_id, "file_name": file_name}
    return mapping


def create_detailed_results_df(
    results: list[dict[str, Any]],
    question_to_file_map: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Create a detailed DataFrame with all evaluation results, enriched with file info."""
    rows: list[dict[str, Any]] = []
    for r in results:
        question = r["question"]
        file_id = ""
        file_name = ""
        if question_to_file_map and question in question_to_file_map:
            file_id = question_to_file_map[question]["file_id"]
            file_name = question_to_file_map[question]["file_name"]

        rows.append({
            "pipeline": r["pipeline_name"],
            "file_id": file_id,
            "file_name": file_name,
            "question": question,
            "verdict": r["verdict"],
            "confidence": r.get("confidence", 0.0),
            "ground_truth": r["ground_truth"],
            "llm_answer": r["llm_answer"],
            "explanation": r["explanation"],
            "missing_info": "; ".join(r.get("missing_information", [])),
        })

    return pd.DataFrame(rows)


def compute_file_metrics(detailed_results: pd.DataFrame) -> pd.DataFrame:
    """Compute performance metrics grouped by file (across all pipelines)."""
    if detailed_results.empty:
        return pd.DataFrame()

    df = detailed_results.copy()
    group = df.groupby(["file_id", "file_name"])  # file_name may be empty if mapping not found
    stats = group.agg({
        "verdict": [
            ("total", "count"),
            ("correct", lambda x: (x == "CORRECT").sum()),
            ("partial", lambda x: (x == "PARTIAL").sum()),
            ("hallucination", lambda x: (x == "HALLUCINATION").sum()),
            ("missed", lambda x: (x == "MISSED").sum()),
        ],
        "confidence": "mean",
    }).round(4)

    stats.columns = ["_".join(col).strip("_") for col in stats.columns]
    stats["correct_rate"] = (stats["verdict_correct"] / stats["verdict_total"]).round(4)
    stats["partial_rate"] = (stats["verdict_partial"] / stats["verdict_total"]).round(4)
    stats["hallucination_rate"] = (stats["verdict_hallucination"] / stats["verdict_total"]).round(4)
    stats["missed_rate"] = (stats["verdict_missed"] / stats["verdict_total"]).round(4)
    stats["success_rate"] = (
        (stats["verdict_correct"] + stats["verdict_partial"]) / stats["verdict_total"]
    ).round(4)

    return stats.reset_index()


def compute_pipeline_file_metrics(detailed_results: pd.DataFrame) -> pd.DataFrame:
    """Compute performance metrics grouped by pipeline and file."""
    if detailed_results.empty:
        return pd.DataFrame()

    df = detailed_results.copy()
    group = df.groupby(["pipeline", "file_id", "file_name"])  # long format
    stats = group.agg({
        "verdict": [
            ("total", "count"),
            ("correct", lambda x: (x == "CORRECT").sum()),
            ("partial", lambda x: (x == "PARTIAL").sum()),
            ("hallucination", lambda x: (x == "HALLUCINATION").sum()),
            ("missed", lambda x: (x == "MISSED").sum()),
        ],
    })
    stats.columns = ["_".join(col).strip("_") for col in stats.columns]
    stats["success_rate"] = (
        (stats["verdict_correct"] + stats["verdict_partial"]) / stats["verdict_total"]
    ).round(4)
    return stats.reset_index()


