"""
AI report generation helpers (Gemini) with a French prompt.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from pathlib import Path

import pandas as pd
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig


async def generate_ai_report_fr(
    global_metrics: dict[str, Any],
    pipeline_metrics: pd.DataFrame,
    detailed_results: pd.DataFrame,
    file_metrics: pd.DataFrame,
    pipeline_file_metrics: pd.DataFrame,
) -> str:
    """Generate a French analysis report using Gemini."""

    prompt = f"""
Tu es un expert data scientist analysant la performance de différents pipelines d'extraction de documents.

## Méthodologie d'évaluation (description factuelle)

Décris succinctement les étapes suivies sans les juger ni les critiquer. Nous avons évalué plusieurs pipelines en:
1. Parsant des documents d'assurance (PDF) avec différentes méthodes
2. Posant des questions ciblées sur la prise en charge et le remboursement
3. Comparant les réponses du LLM (basées sur les documents parsés) au jeu de vérité terrain
4. Attribuant un verdict selon 4 catégories:
   - CORRECT: Concordance parfaite avec la vérité terrain
   - PARTIAL: Bonne direction mais informations clés manquantes
   - HALLUCINATION: Informations incorrectes ou non étayées
   - MISSED: Indique "non disponible" alors que l'information existe

## Indicateurs globaux

{json.dumps(global_metrics, indent=2, ensure_ascii=False)}

## Comparaison des pipelines

{pipeline_metrics.to_string()}

## Performance par fichier

{file_metrics.to_string()}

## Pipeline x Fichier (taux de succès)

{pipeline_file_metrics.pivot(index='pipeline', columns='file_name', values='success_rate').to_string() if not pipeline_file_metrics.empty else "Aucune donnée pipeline x fichier"}

## Exemples de résultats détaillés (10 premiers)

{detailed_results.head(10).to_string()}

## Ta mission

Rédige un rapport d'analyse structuré en français, incluant:

1. Résumé exécutif: constats clés et recommandations (2–3 paragraphes)
2. Description de la méthodologie: reformulation neutre et factuelle (sans évaluation)
3. Analyse de performance:
   - Comparaison objective des pipelines
   - Motifs récurrents de réussite/échec
   - Corrélation entre score de confiance et verdict
4. Analyse des causes:
   - Hypothèses sur les écarts de performance entre pipelines
   - Caractéristiques documentaires influentes (structure, tableaux, formatage)
5. Recommandations:
   - Pipeline(s) à privilégier et justification
   - Idées d'approches hybrides
   - Pistes d'amélioration de l'évaluation
6. Analyse par type de verdict:
   - PARTIAL: informations manquantes typiques
   - MISSED: angles morts systématiques éventuels
   - HALLUCINATION: sources fréquentes d'erreurs
7. Aperçus par fichier:
   - Variabilité entre fichiers et explications plausibles

Utilise un style clair, structuré en markdown, avec des listes lorsque pertinent.
"""

    client = genai.Client(vertexai=True, project="probtp-poc-prod", location="global")
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-09-2025",
            contents=prompt,
            config=GenerateContentConfig(
                thinking_config=ThinkingConfig(thinking_budget=4096)
            ),
        )
        return getattr(response, "text", "").strip()
    finally:
        if hasattr(client, "close"):
            if asyncio.iscoroutinefunction(client.close):
                await client.close()
            else:
                client.close()


async def summarize_pipeline_files_fr(pipelines_dir: Path) -> dict[str, str]:
    """Summarize each pipeline Python file in French using Gemini Flash.

    Returns mapping of file stem -> concise French summary (markdown bullets).
    """
    summaries: dict[str, str] = {}

    if not pipelines_dir.exists() or not pipelines_dir.is_dir():
        return summaries

    client = genai.Client(vertexai=True, project="probtp-poc-prod", location="global")
    try:
        for py_file in sorted(pipelines_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue

            code_text = py_file.read_text(encoding="utf-8")
            prompt = f"""
Tu es un assistant technique. Résume ce script Python de pipeline d'extraction en français.

Fournis une synthèse courte et structurée (5–8 puces max):
- Objet du pipeline et cas d'usage
- Entrées attendues et sorties produites
- Principales techniques/étapes (OCR, parsing, post-traitement LLM, etc.)
- Dépendances externes notables (API/LLM/bibliothèques)
- Hypothèses/limitations connues

Contraintes:
- Style concis, neutre et factuel (pas de jugement)
- Pas de code, pas d’implémentation détaillée

<script>
{code_text}
</script>
"""
            try:
                resp = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=GenerateContentConfig(
                        thinking_config=ThinkingConfig(thinking_budget=256),
                        max_output_tokens=400,
                        temperature=0.2,
                    ),
                )
                summary = getattr(resp, "text", "").strip()
            except Exception:
                summary = "Résumé indisponible."

            summaries[py_file.stem] = summary
    finally:
        if hasattr(client, "close"):
            if asyncio.iscoroutinefunction(client.close):
                await client.close()
            else:
                client.close()

    return summaries


