"""Taxonomy-First Pipeline for Insurance Contract Comparison.

This pipeline implements a taxonomy-first approach:
1. Extract universal taxonomy from ProBTP (reference document)
2. Extract values from both vendors mapped to taxonomy (loop per category)
3. Assemble comparison tables programmatically
4. Generate analysis and reports

Key benefits:
- Reduced LLM cognitive load (separate structure from values)
- Clear separation of universal vs. vendor-specific
- Modular checkpointing for debugging
- Selective re-run capability
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse, observe
from langfuse._client.observe import F

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize Langfuse
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# Default categories to analyze
DEFAULT_CATEGORIES = [
    "Soins Courants",
    "Hospitalisation",
    "Optique",
    "Soins Dentaires",
    "Audiologie",
    "Prestations Complémentaires",
]

# Category to ProBTP level type mapping
# "S" levels = Soins (care) categories
# "P" levels = Prévoyance (prevention/specialized) categories
CATEGORY_LEVEL_MAPPING = {
    "Soins courants": "S",
    "Hospitalisation": "S",
    "Optique": "P",
    "Dentaire": "P",
    "Aides auditives": "P",
    "Prestations complémentaires": "P",
}

from prompts.taxonomy_first.analysis_prompt import (
    TaxonomyFirstAnalysisOutput,
    create_taxonomy_first_analysis_prompt,
)
from prompts.taxonomy_first.summary_prompt import (
    ComparisonSummary,
    create_summary_prompt,
)
from prompts.taxonomy_first.taxonomy_extraction_prompt import (
    ProBTPTaxonomy,
    create_taxonomy_extraction_prompt,
)
from prompts.taxonomy_first.value_extraction_prompt import (
    CategoryValueExtraction,
    create_value_extraction_prompt,
)
from utils.bounding_box_enricher import (
    enrich_comparison_table_with_bounding_boxes,
)
from utils.comparison_document_builder import (
    ComparisonDocument,
    build_comparison_document,
    prepare_for_llm,
)
from utils.page_dimensions_generator import (
    generate_page_dimensions_cache,
    load_page_dimensions_cache,
)
from utils.document_loader import ParsedDocument
from utils.gemini_client import generate_with_reasoning
from utils.json_formatters import (
    analysis_to_markdown,
    comparison_table_to_markdown,
    summary_to_markdown,
)
from utils.markdown_generator import (
    generate_comparison_markdown,
)
from utils.report_formatter import (
    create_report_metadata,
    save_report,
)
from utils.table_builder_from_analysis import (
    build_table_from_analysis,
)


def extract_leaves_from_flat_taxonomy(
    nodes: list[dict[str, Any]], parent_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Extract all leaf nodes that are descendants of a given parent from a flat taxonomy.

    Args:
        nodes: Flat list of all taxonomy nodes
        parent_id: Parent node ID to extract leaves for (None for all top-level categories)

    Returns:
        List of leaf nodes (nodes where is_leaf=True) under the specified parent
    """
    leaves = []

    # If parent_id is specified, find all descendants
    if parent_id is not None:
        # Get all nodes that are descendants of parent_id
        descendants = get_descendants(nodes, parent_id)
        candidate_nodes = descendants
    else:
        # Extract from all nodes
        candidate_nodes = nodes

    # Filter for leaves
    for node in candidate_nodes:
        if node.get("is_leaf", False):
            leaves.append(
                {
                    "path": node["path"],
                    "leaf_id": node["node_id"],
                    "description": node["description"],
                    "securite_sociale_coverage": node.get("securite_sociale_coverage"),
                }
            )

    return leaves


def get_descendants(
    nodes: list[dict[str, Any]], parent_id: str
) -> list[dict[str, Any]]:
    """
    Get all descendant nodes of a given parent from a flat list.

    Preserves the original depth-first order from the taxonomy.

    Args:
        nodes: Flat list of all taxonomy nodes (in depth-first order)
        parent_id: Parent node ID

    Returns:
        List of all descendants (including direct children and their descendants) in original order
    """
    # Build ancestor lookup for efficient checking
    descendant_ids = set()
    nodes_by_id = {node["node_id"]: node for node in nodes}

    # Find all descendants using BFS to build the ID set
    queue = [parent_id]
    while queue:
        current_id = queue.pop(0)
        for node in nodes:
            node_id = node["node_id"]
            if node.get("parent_id") == current_id and node_id not in descendant_ids:
                descendant_ids.add(node_id)
                queue.append(node_id)

    # Return descendants in original order from nodes list
    descendants = [node for node in nodes if node["node_id"] in descendant_ids]

    return descendants


def filter_probtp_levels_for_category(
    category_name: str, all_probtp_levels: list[str] | None
) -> list[str] | None:
    """
    Filter ProBTP levels appropriate for a given category.

    Args:
        category_name: Category name
        all_probtp_levels: All ProBTP levels provided

    Returns:
        Filtered list of levels appropriate for the category, or None if no levels provided
    """
    if not all_probtp_levels:
        return None

    # Get the level type for this category (S or P)
    level_type = CATEGORY_LEVEL_MAPPING.get(category_name)

    if not level_type:
        # Category not in mapping, return all levels
        return all_probtp_levels

    # Filter levels that start with the appropriate type
    filtered_levels = [
        level for level in all_probtp_levels if level.startswith(level_type)
    ]

    return filtered_levels if filtered_levels else None


class TaxonomyFirstPipeline:
    """
    Taxonomy-first pipeline for insurance contract comparison.

    Workflow:
    1. Extract ProBTP taxonomy (reference structure)
    2. For each category: extract values from ProBTP and AXA
    3. Assemble comparison tables programmatically
    4. Generate analysis and markdown reports
    """

    def __init__(
        self,
        probtp_doc_path: str | Path,
        axa_doc_path: str | Path,
        output_dir: str | Path,
        model_name: str = "gemini-2.5-flash",
        categories_to_process: list[str] | None = None,
        language: str = "French (France)",
    ):
        """
        Initialize pipeline.

        Args:
            probtp_doc_path: Path to ProBTP parsed document JSON
            axa_doc_path: Path to AXA parsed document JSON
            output_dir: Output directory for results
            model_name: Google GenAI model name
            categories_to_process: List of category IDs to process (e.g., ["hospitalisation", "optique"])
                                  If None, processes all categories found in taxonomy
            language: Output language for reports
        """
        self.probtp_doc_path = Path(probtp_doc_path)
        self.axa_doc_path = Path(axa_doc_path)
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.categories_to_process = categories_to_process
        self.language = language

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.output_dir / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

        # Load documents
        print("Loading documents...")
        self.probtp_doc = ParsedDocument(self.probtp_doc_path)
        self.axa_doc = ParsedDocument(self.axa_doc_path)

        # Pipeline state
        self.taxonomy: dict[str, Any] | None = None
        self.extractions: dict[
            str, dict[str, Any]
        ] = {}  # category_id -> {probtp: ..., axa: ...}
        self.comparison_documents: dict[
            str, dict[str, Any]
        ] = {}  # category_id -> ComparisonDocument
        self.leaf_analyses: dict[
            str, dict[str, Any]
        ] = {}  # category_id -> TaxonomyFirstAnalysisOutput (leaf-level analyses)
        self.comparison_tables: dict[
            str, dict[str, Any]
        ] = {}  # category_id -> ComparisonTable
        self.analyses: list[dict[str, Any]] = []  # Array of {category, annotated_table}
        self.general_summary: dict[str, Any] | None = None  # ComparisonSummary
        self.overall_recommendation: str | None = None

    @observe(name="taxonomy_first_pipeline")
    async def run(
        self,
        probtp_levels: list[str] | None = None,
        axa_levels: list[str] | None = None,
        skip_taxonomy: bool = False,
        skip_extraction: bool = False,
        skip_assembly: bool = False,
        skip_analysis: bool = False,
        skip_summary: bool = False,
        skip_recommendation: bool = False,
        skip_grounding: bool = False,
    ) -> dict[str, Any]:
        """
        Run the complete pipeline.

        Args:
            probtp_levels: ProBTP policy levels to extract (will be filtered per category)
            axa_levels: AXA policy levels to extract
            skip_taxonomy: Skip taxonomy extraction (load from checkpoint)
            skip_extraction: Skip value extraction (load from checkpoint)
            skip_assembly: Skip table assembly (load from checkpoint)
            skip_analysis: Skip analysis generation (load from checkpoint)
            skip_summary: Skip summary generation (load from checkpoint)
            skip_recommendation: Skip recommendation generation
            skip_grounding: Skip bounding box enrichment

        Returns:
            Pipeline results dict with file paths
        """
        # Initialize Langfuse trace for entire pipeline
        langfuse.update_current_trace(
            name="taxonomy_first_pipeline",
            metadata={
                "pipeline_type": "taxonomy_first",
                "probtp_document": self.probtp_doc.name,
                "axa_document": self.axa_doc.name,
                "probtp_levels": probtp_levels,
                "axa_levels": axa_levels,
                "categories_to_process": self.categories_to_process,
                "skip_taxonomy": skip_taxonomy,
                "skip_extraction": skip_extraction,
                "skip_assembly": skip_assembly,
                "skip_analysis": skip_analysis,
            },
        )
        print(f"\n{'=' * 80}")
        print("TAXONOMY-FIRST PIPELINE")
        print(f"{'=' * 80}")
        print(f"ProBTP document: {self.probtp_doc.name}")
        print(f"AXA document: {self.axa_doc.name}")
        print(f"ProBTP levels: {probtp_levels}")
        print(f"AXA levels: {axa_levels}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'=' * 80}\n")

        # Phase 1: Extract taxonomy
        taxonomy_checkpoint = self.tmp_dir / "taxonomy.json"
        if not skip_taxonomy and not taxonomy_checkpoint.exists():
            print(f"\n{'─' * 80}")
            print("PHASE 1: Taxonomy Extraction")
            print(f"{'─' * 80}")
            self.taxonomy = await self._extract_taxonomy()
            self._save_checkpoint("taxonomy", self.taxonomy)
        else:
            if taxonomy_checkpoint.exists():
                print("\n⏩ Taxonomy checkpoint found, loading from checkpoint")
            else:
                print("\n⏩ Skipping taxonomy extraction (loading from checkpoint)")
            self.taxonomy = self._load_checkpoint("taxonomy")

        # Filter top-level categories if specified
        all_nodes = self.taxonomy["nodes"]
        top_level_categories = [
            node for node in all_nodes if node.get("parent_id") == "_root_"
        ]
        print(f"\n📋 Top-level categories: {[c['name'] for c in top_level_categories]}")

        if self.categories_to_process:
            print(
                f"\n📋 Processing {len(self.categories_to_process)} categories: {self.categories_to_process}"
            )
            categories = [
                cat
                for cat in top_level_categories
                if cat["name"].lower()
                in [c.lower() for c in self.categories_to_process]
            ]
            print(
                f"\n📋 Processing {len(categories)} categories: {[c['node_id'] for c in categories]}"
            )
        else:
            categories = top_level_categories
            print(f"\n📋 Processing all {len(categories)} categories")

        # Phase 2: Extract values per category (grouped by provider for prompt caching)
        if not skip_extraction:
            print(f"\n{'─' * 80}")
            print("PHASE 2: Value Extraction")
            print(f"{'─' * 80}")

            # Prepare category data
            category_data = []
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                # Extract leaves from flat taxonomy for this category
                category_leaves = extract_leaves_from_flat_taxonomy(
                    all_nodes, category_id
                )

                # Filter ProBTP levels for this category
                category_probtp_levels = filter_probtp_levels_for_category(
                    category_name, probtp_levels
                )

                category_data.append({
                    "id": category_id,
                    "name": category_name,
                    "leaves": category_leaves,
                    "probtp_levels": category_probtp_levels,
                })

                print(f"\n📦 Category: {category_name} ({category_id})")
                print(f"   Leaves: {len(category_leaves)}")
                if category_probtp_levels and category_probtp_levels != probtp_levels:
                    print(
                        f"   → Filtered ProBTP levels for {category_name}: {category_probtp_levels}"
                    )

            # Extract all ProBTP values first (enables prompt caching)
            print(f"\n{'─' * 40}")
            print("Extracting ProBTP values (all categories)")
            print(f"{'─' * 40}")
            for cat_data in category_data:
                probtp_extraction = await self._extract_values(
                    vendor="ProBTP",
                    vendor_doc=self.probtp_doc,
                    category_id=cat_data["id"],
                    category_name=cat_data["name"],
                    category_leaves=cat_data["leaves"],
                    policy_levels=cat_data["probtp_levels"],
                    full_taxonomy_nodes=all_nodes,
                )
                self._save_checkpoint(f"{cat_data['id']}_probtp_values", probtp_extraction)

                if cat_data["id"] not in self.extractions:
                    self.extractions[cat_data["id"]] = {}
                self.extractions[cat_data["id"]]["probtp"] = probtp_extraction

                print(
                    f"   ✓ {cat_data['name']}: {len(probtp_extraction['extracted_values'])} leaves"
                )

            # Then extract all AXA values (enables prompt caching)
            print(f"\n{'─' * 40}")
            print("Extracting AXA values (all categories)")
            print(f"{'─' * 40}")
            for cat_data in category_data:
                axa_extraction = await self._extract_values(
                    vendor="AXA",
                    vendor_doc=self.axa_doc,
                    category_id=cat_data["id"],
                    category_name=cat_data["name"],
                    category_leaves=cat_data["leaves"],
                    policy_levels=axa_levels,
                    full_taxonomy_nodes=all_nodes,
                )
                self._save_checkpoint(f"{cat_data['id']}_axa_values", axa_extraction)

                self.extractions[cat_data["id"]]["axa"] = axa_extraction

                print(
                    f"   ✓ {cat_data['name']}: {len(axa_extraction['extracted_values'])} leaves"
                )
        else:
            print("\n⏩ Skipping value extraction (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                probtp_extraction = self._load_checkpoint(
                    f"{category_id}_probtp_values"
                )
                axa_extraction = self._load_checkpoint(f"{category_id}_axa_values")
                self.extractions[category_id] = {
                    "probtp": probtp_extraction,
                    "axa": axa_extraction,
                }

        # Phase 3: Build comparison documents
        if not skip_assembly:
            print(f"\n{'─' * 80}")
            print("PHASE 3: Comparison Document Building")
            print(f"{'─' * 80}")
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n🔧 Building comparison document: {category_name}")

                # Extract leaves for this category
                category_leaves = extract_leaves_from_flat_taxonomy(
                    all_nodes, category_id
                )

                # Create category dict with leaves
                category_with_leaves = {
                    **category,
                    "leaves": category_leaves,
                    "category_name": category_name,
                }

                comparison_doc = build_comparison_document(
                    category_taxonomy=category_with_leaves,
                    probtp_extraction=self.extractions[category_id]["probtp"],
                    axa_extraction=self.extractions[category_id]["axa"],
                )

                self.comparison_documents[category_id] = comparison_doc.model_dump()
                self._save_checkpoint(
                    f"{category_id}_comparison_document", comparison_doc.model_dump()
                )

                print(f"   ✓ Leaves: {len(comparison_doc.leaves)}")
        else:
            print(
                "\n⏩ Skipping comparison document building (loading from checkpoints)"
            )
            for category in categories:
                category_id = category["node_id"]
                comparison_doc = self._load_checkpoint(
                    f"{category_id}_comparison_document"
                )
                self.comparison_documents[category_id] = comparison_doc

        # Phase 4: Generate analysis
        if not skip_analysis:
            print(f"\n{'─' * 80}")
            print("PHASE 4: Analysis Generation")
            print(f"{'─' * 80}")
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n📊 Analyzing: {category_name}")

                analysis = await self._generate_analysis(
                    category_name=category_name,
                    comparison_document=self.comparison_documents[category_id],
                )

                self.leaf_analyses[category_id] = analysis
                self._save_checkpoint(f"{category_id}_analysis", analysis)

                print("   ✓ Analysis complete")
                print(
                    f"      Leaf comparisons: {len(analysis.get('leaf_comparisons', []))}"
                )
        else:
            print("\n⏩ Skipping analysis (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                analysis = self._load_checkpoint(f"{category_id}_analysis")
                self.leaf_analyses[category_id] = analysis

        # Phase 5: Build comparison tables from analysis
        print(f"\n{'─' * 80}")
        print("PHASE 5: Table Assembly from Analysis")
        print(f"{'─' * 80}")
        for category in categories:
            category_id = category["node_id"]
            category_name = category["name"]

            print(f"\n🔧 Assembling table: {category_name}")

            # Parse analysis output
            analysis_output = TaxonomyFirstAnalysisOutput.model_validate(
                self.leaf_analyses[category_id]
            )

            comparison_table = build_table_from_analysis(
                comparison_document=self.comparison_documents[category_id],
                analysis=analysis_output,
                taxonomy_nodes=all_nodes,  # Pass full taxonomy for hierarchy-aware table building
            )

            self.comparison_tables[category_id] = comparison_table
            self._save_checkpoint(f"{category_id}_comparison_table", comparison_table)

            print(f"   ✓ Rows: {len(comparison_table['rows'])}")
            print(f"   ✓ Columns: {comparison_table['metadata']['total_columns']}")

        # Phase 6: Generate category markdown reports
        print(f"\n{'─' * 80}")
        print("PHASE 6: Category Report Generation")
        print(f"{'─' * 80}")

        for category in categories:
            category_id = category["node_id"]
            category_name = category["name"]

            print(f"\n📝 Generating report: {category_name}")

            # Generate markdown
            markdown = generate_comparison_markdown(
                comparison_table=self.comparison_tables[category_id],
                analysis=self.leaf_analyses[category_id],
            )

            # Save markdown
            markdown_path = self.output_dir / f"{category_id}_comparison.md"
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            print(f"   ✓ Markdown saved: {markdown_path.name}")

        # Phase 7: Generate general summary
        if not skip_summary:
            print(f"\n{'─' * 80}")
            print("PHASE 7: General Summary Generation")
            print(f"{'─' * 80}")
            self.general_summary = await self._generate_summary(
                all_analyses=list(self.leaf_analyses.values())
            )
            self._save_checkpoint("general_summary", self.general_summary)
            print("   ✓ Summary generated")
        else:
            print("\n⏩ Skipping summary generation (loading from checkpoint)")
            summary_checkpoint = self.tmp_dir / "general_summary.json"
            if summary_checkpoint.exists():
                self.general_summary = self._load_checkpoint("general_summary")
                print("   ✓ Summary loaded from checkpoint")
            else:
                print("   ⚠️  No summary checkpoint found, setting to None")
                self.general_summary = None

        # Phase 8: Generate overall recommendation
        if not skip_recommendation:
            print(f"\n{'─' * 80}")
            print("PHASE 8: Overall Recommendation Generation")
            print(f"{'─' * 80}")
            self.overall_recommendation = await self._generate_recommendation(
                all_analyses=list(self.leaf_analyses.values())
            )
            self._save_checkpoint("general_recommendation", self.overall_recommendation)
            print(f"   ✓ Recommendation generated ({len(self.overall_recommendation)} chars)")
        else:
            print("\n⏩ Skipping recommendation generation")
            recommendation_checkpoint = self.tmp_dir / "general_recommendation.json"
            if recommendation_checkpoint.exists():
                self.overall_recommendation = self._load_checkpoint("general_recommendation")
                print(f"   ✓ Recommendation loaded from checkpoint ({len(self.overall_recommendation)} chars)")
            else:
                print("   ⚠️  No recommendation checkpoint found, setting to empty string")
                self.overall_recommendation = ""

        # Phase 9: Assemble final report
        print(f"\n{'─' * 80}")
        print("PHASE 9: Final Report Assembly")
        print(f"{'─' * 80}")

        # Build report filename
        probtp_level_str = "_".join(probtp_levels) if probtp_levels else "default"
        probtp_level_str = probtp_level_str.replace("+", "plus").replace(" ", "_")
        axa_level_str = "_".join(axa_levels) if axa_levels else "default"
        axa_level_str = axa_level_str.replace(" ", "_")
        final_report_path = (
            self.output_dir
            / f"comparison_report_ProBTP_{probtp_level_str}_vs_AXA_{axa_level_str}.md"
        )

        # Create metadata (needed for category ordering)
        metadata = create_report_metadata(
            probtp_doc_name=self.probtp_doc.name,
            axa_doc_name=self.axa_doc.name,
            model=self.model_name,
            probtp_levels=probtp_levels,
            axa_levels=axa_levels,
            categories=[cat["name"] for cat in categories],
        )

        # Convert to markdown
        report_sections = []
        annex_sections = []  # Store detailed comparisons for annex

        # Summary section
        if self.general_summary:
            report_sections.append(summary_to_markdown(self.general_summary))
            report_sections.append("\n---\n")

        # Category sections (with comparison tables)
        # Use category order from metadata, not dict keys
        category_names_ordered = metadata.get("Categories", "").split(", ")
        category_map = {cat["name"]: cat["node_id"] for cat in categories}

        from utils.json_formatters import detailed_leaf_comparisons_to_markdown

        for category_name in category_names_ordered:
            if not category_name or category_name not in category_map:
                continue

            category_id = category_map[category_name]

            if category_id in self.leaf_analyses:
                # Add category header (H2 level)
                report_sections.append(f"## {category_name}\n")

                # Add comparison table with French header
                if category_id in self.comparison_tables:
                    report_sections.append(f"### Tableau Récapitulatif pour {category_name}\n")
                    # Generate table without its own header
                    table_md = comparison_table_to_markdown(self.comparison_tables[category_id], include_row_comparison=False)
                    # Remove category header if present
                    table_lines = table_md.split('\n')
                    if table_lines and table_lines[0].startswith('### '):
                        table_md = '\n'.join(table_lines[1:])
                    report_sections.append(table_md)
                    report_sections.append("\n")

                    # Add link to annex
                    # Create anchor-friendly ID (lowercase, replace spaces with hyphens)
                    category_anchor = category_name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
                    report_sections.append(f"*→ Voir [Comparaisons détaillées - {category_name}](#comparaisons-détaillées---{category_anchor}) en annexe*\n")
                    report_sections.append("\n")

                # Store detailed leaf comparisons for annex
                if category_id in self.comparison_documents:
                    detailed_md = detailed_leaf_comparisons_to_markdown(
                        self.comparison_documents[category_id],
                        self.leaf_analyses[category_id],
                        self.comparison_tables[category_id],
                    )
                    # Add to annex sections with back-reference
                    annex_sections.append(f"### Comparaisons Détaillées - {category_name}\n")
                    annex_sections.append(detailed_md)
                    annex_sections.append("\n")
                    annex_sections.append(f"*← Retour au [Tableau récapitulatif](#{ category_name.lower().replace(' ', '-').replace('é', 'e').replace('è', 'e')})*\n")
                    annex_sections.append("\n---\n")

                # Add analysis sections (without the category header since we already added H2)
                analysis_md = analysis_to_markdown(self.leaf_analyses[category_id])
                # Remove the first line (H2 category header) from analysis_to_markdown output
                analysis_lines = analysis_md.split('\n')
                if analysis_lines and analysis_lines[0].startswith('## '):
                    # Remove H2 header line
                    analysis_md = '\n'.join(analysis_lines[1:])
                report_sections.append(analysis_md)
                report_sections.append("\n---\n")

        # Recommendation section
        if self.overall_recommendation:
            report_sections.append("## Recommandations Globales\n")
            report_sections.append(self.overall_recommendation)
            report_sections.append("\n")

        # Add annex section at the end
        if annex_sections:
            report_sections.append("\n---\n")
            report_sections.append("## Annexe: Comparaisons Détaillées\n")
            report_sections.extend(annex_sections)

        # Build full report
        full_report = "---\n"
        for key, value in metadata.items():
            if isinstance(value, list):
                full_report += f"{key}: {', '.join(value)}\n"
            else:
                full_report += f"{key}: {value}\n"
        full_report += "---\n\n"
        full_report += "\n".join(report_sections)

        # Save report
        save_report(full_report, final_report_path)
        print(f"   ✓ Final report saved: {final_report_path.name}")

        # Phase 10: Build global JSON with grounding
        print(f"\n{'─' * 80}")
        print("PHASE 10: Global JSON with Grounding")
        print(f"{'─' * 80}")

        # Build JSON output path
        json_output_path = final_report_path.with_suffix(".json")
        json_output_path_before = final_report_path.with_suffix(".before_bbox.json")

        # Save version without bounding boxes first
        analyses_array_before = []
        for category in categories:
            category_id = category["node_id"]
            category_name = category["name"]
            if category_id in self.comparison_tables:
                analysis_entry = {
                    "category": category_name,
                    "annotated_table": self.comparison_tables[category_id],
                }
                if category_id in self.leaf_analyses:
                    analysis_entry.update(self.leaf_analyses[category_id])
                analyses_array_before.append(analysis_entry)

        json_data_before = {
            "metadata": metadata,
            "taxonomy": self.taxonomy,
            "extractions": self.extractions,
            "comparison_documents": self.comparison_documents,
            "leaf_analyses": self.leaf_analyses,
            "analyses": analyses_array_before,
            "comparison_tables": list(self.comparison_tables.values()),
            "general_summary": self.general_summary,
            "overall_recommendation": self.overall_recommendation,
        }

        with open(json_output_path_before, "w", encoding="utf-8") as f:
            json.dump(json_data_before, f, ensure_ascii=False, indent=2)
        print(f"   ✓ JSON data (before bbox) saved: {json_output_path_before.name}")

        # Enrich with bounding boxes
        if not skip_grounding:
            print("   → Adding bounding boxes from source documents...")

            # Generate/load page dimensions cache
            page_dims_cache_path = self.output_dir / "page_dimensions.json"

            if not page_dims_cache_path.exists():
                print("   → Generating page dimensions cache...")

                # Map JSON paths to PDF paths
                # JSON: output/landing_ai_xtd/File #1 - ....json
                # PDF: documents/File #1 - ....pdf
                base_dir = self.probtp_doc_path.parent.parent.parent
                documents_dir = base_dir / "documents"

                probtp_pdf_path = documents_dir / f"{self.probtp_doc.name}.pdf"
                axa_pdf_path = documents_dir / f"{self.axa_doc.name}.pdf"

                # Build PDF paths map
                pdf_paths = {
                    self.probtp_doc.name: probtp_pdf_path,
                    self.axa_doc.name: axa_pdf_path,
                }

                # Generate cache
                page_dimensions_cache = generate_page_dimensions_cache(
                    pdf_paths,
                    page_dims_cache_path
                )
            else:
                print("   → Loading page dimensions cache...")
                page_dimensions_cache = load_page_dimensions_cache(page_dims_cache_path)

            # FIRST: Enrich comparison_tables dict entries
            # This ensures both comparison_tables and analyses use the same enriched data
            print("   → Enriching comparison_tables...")
            all_grounding_stats = []
            for category in categories:
                category_id = category["node_id"]
                if category_id in self.comparison_tables:
                    enriched_table, grounding_stats = enrich_comparison_table_with_bounding_boxes(
                        self.comparison_tables[category_id],
                        self.probtp_doc_path,
                        self.axa_doc_path,
                        page_dimensions_cache
                    )
                    # Update in-place so both comparison_tables and analyses reference the same enriched data
                    self.comparison_tables[category_id] = enriched_table
                    all_grounding_stats.append(grounding_stats)

            # THEN: Build analyses array from already-enriched comparison_tables
            print("   → Building analyses array from enriched tables...")
            analyses_array = []
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]
                if category_id in self.comparison_tables:
                    # Now using enriched table (already has bounding boxes)
                    analysis_entry = {
                        "category": category_name,
                        "annotated_table": self.comparison_tables[category_id],
                    }
                    # Add analysis output fields if available
                    if category_id in self.leaf_analyses:
                        analysis_entry.update(self.leaf_analyses[category_id])
                    analyses_array.append(analysis_entry)
            self.analyses = analyses_array

            # Prepare final JSON data with enriched tables
            json_data = {
                "metadata": metadata,
                "taxonomy": self.taxonomy,
                "extractions": self.extractions,
                "comparison_documents": self.comparison_documents,
                "leaf_analyses": self.leaf_analyses,
                "analyses": self.analyses,  # Now has enriched tables
                "comparison_tables": list(self.comparison_tables.values()),  # Also enriched
                "general_summary": self.general_summary,
                "overall_recommendation": self.overall_recommendation,
            }

            # Save enriched version
            with open(json_output_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            print(f"   ✓ JSON data (with bounding boxes) saved: {json_output_path.name}")

            # Save grounding statistics
            grounding_stats_path = json_output_path.with_suffix(".grounding_stats.json")
            with open(grounding_stats_path, "w", encoding="utf-8") as f:
                json.dump(all_grounding_stats, f, ensure_ascii=False, indent=2)
            print(f"   ✓ Grounding statistics saved: {grounding_stats_path.name}")
        else:
            print("   ⏩ Skipping bounding box enrichment")
            # Build analyses array without enrichment
            analyses_array = []
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]
                if category_id in self.comparison_tables:
                    analysis_entry = {
                        "category": category_name,
                        "annotated_table": self.comparison_tables[category_id],
                    }
                    if category_id in self.leaf_analyses:
                        analysis_entry.update(self.leaf_analyses[category_id])
                    analyses_array.append(analysis_entry)
            self.analyses = analyses_array

            # Prepare JSON data without enrichment
            json_data = {
                "metadata": metadata,
                "taxonomy": self.taxonomy,
                "extractions": self.extractions,
                "comparison_documents": self.comparison_documents,
                "leaf_analyses": self.leaf_analyses,
                "analyses": self.analyses,
                "comparison_tables": list(self.comparison_tables.values()),
                "general_summary": self.general_summary,
                "overall_recommendation": self.overall_recommendation,
            }

            # Save without enrichment
            with open(json_output_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            print(f"   ✓ JSON data saved: {json_output_path.name}")

        # Pipeline complete
        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"Categories processed: {len(categories)}")
        print(f"Output directory: {self.output_dir}")
        print(f"Final report: {final_report_path}")
        print(f"JSON output: {json_output_path}")
        print(f"{'=' * 80}\n")

        return {
            "taxonomy": self.taxonomy,
            "extractions": self.extractions,
            "comparison_documents": self.comparison_documents,
            "leaf_analyses": self.leaf_analyses,
            "analyses": self.analyses,
            "comparison_tables": self.comparison_tables,
            "general_summary": self.general_summary,
            "overall_recommendation": self.overall_recommendation,
            "final_report_path": str(final_report_path),
            "json_output_path": str(json_output_path),
        }

    @observe(name="extract_taxonomy")
    async def _extract_taxonomy(self) -> dict[str, Any]:
        """Extract ProBTP taxonomy."""
        print("Extracting taxonomy from ProBTP document...")

        probtp_markdown = self.probtp_doc.get_full_markdown()
        prompt = create_taxonomy_extraction_prompt(probtp_markdown)

        print(f"   Model: {self.model_name}")
        print(f"   Prompt length: {len(prompt)} chars")

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "taxonomy_extraction",
                "model": self.model_name,
                "prompt_length": len(prompt),
                "source_document": self.probtp_doc.name,
            }
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model="gemini-2.5-pro",
            thinking_budget=4096,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=ProBTPTaxonomy.model_json_schema(),
            use_vertex=False,
        )

        taxonomy = json.loads(response)

        all_nodes = taxonomy["nodes"]
        top_level_categories = [
            node for node in all_nodes if node.get("parent_id") == "_root_"
        ]

        print(
            f"   ✓ Extracted {len(top_level_categories)} top-level categories ({len(all_nodes)} total nodes)"
        )

        # Extract leaves from flat taxonomy and count them per category
        total_leaves = 0
        for cat in top_level_categories:
            cat_leaves = extract_leaves_from_flat_taxonomy(all_nodes, cat["node_id"])
            total_leaves += len(cat_leaves)
            print(f"     - {cat['name']}: {len(cat_leaves)} leaves")

        # Update trace with results
        langfuse.update_current_trace(
            metadata={
                "phase": "taxonomy_extraction",
                "categories_count": len(top_level_categories),
                "total_nodes": len(all_nodes),
                "total_leaves": total_leaves,
            }
        )

        return taxonomy

    @observe(name="extract_values")
    async def _extract_values(
        self,
        vendor: str,
        vendor_doc: ParsedDocument,
        category_id: str,
        category_name: str,
        category_leaves: list[dict[str, Any]],
        policy_levels: list[str] | None = None,
        full_taxonomy_nodes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Extract values for a category from vendor document."""
        print(f"   Extracting {vendor} values for {category_name}...")

        vendor_markdown = vendor_doc.get_markdown_with_expanded_tables()
        prompt = create_value_extraction_prompt(
            vendor=vendor,
            vendor_markdown=vendor_markdown,
            category_id=category_id,
            category_name=category_name,
            policy_level=policy_levels[0] if policy_levels else "Unknown",
            taxonomy_leaves=category_leaves,
            full_taxonomy_nodes=full_taxonomy_nodes,
        )

        print(f"      Model: {self.model_name}")
        print(f"      Taxonomy leaves: {len(category_leaves)}")

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "value_extraction",
                "vendor": vendor,
                "category": category_name,
                "category_id": category_id,
                "policy_levels": policy_levels,
                "taxonomy_leaves_count": len(category_leaves),
                "model": self.model_name,
            }
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model="gemini-2.5-pro",
            thinking_budget=2048,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=CategoryValueExtraction.model_json_schema(),
            use_vertex=False,
        )

        extraction = json.loads(response)

        # Report unmappable items if any
        unmappable = extraction.get("unmappable_items") or []
        if unmappable:
            print(f"      ⚠️  {len(unmappable)} unmappable items:")
            for item in unmappable[:3]:  # Show first 3
                print(f"         - {item['description']}")
            if len(unmappable) > 3:
                print(f"         ... and {len(unmappable) - 3} more")

        # Update trace with results
        langfuse.update_current_trace(
            metadata={
                "extracted_values_count": len(extraction.get("extracted_values") or []),
                "unmappable_items_count": len(unmappable),
            }
        )

        return extraction

    @observe(name="generate_analysis")
    async def _generate_analysis(
        self,
        category_name: str,
        comparison_document: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate analysis for comparison document."""
        # Validate and prepare comparison document for LLM (strip source_cell_ids)
        comparison_doc_obj = ComparisonDocument.model_validate(comparison_document)
        llm_ready_doc = prepare_for_llm(comparison_doc_obj)

        prompt = create_taxonomy_first_analysis_prompt(
            comparison_document=llm_ready_doc,
        )

        print(f"      Model: {self.model_name}")

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "analysis_generation",
                "category": category_name,
                "model": self.model_name,
                "leaves_count": len(comparison_document.get("leaves", [])),
            }
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=4096,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=TaxonomyFirstAnalysisOutput.model_json_schema(),
        )

        analysis = json.loads(response)

        # Update trace with results
        langfuse.update_current_trace(
            metadata={
                "analysis_generated": True,
                "leaf_comparisons_count": len(analysis.get("leaf_comparisons", [])),
                "has_key_differences": "key_differences" in analysis,
            }
        )

        return analysis

    @observe(name="generate_summary")
    async def _generate_summary(
        self,
        all_analyses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate general summary from all category analyses."""
        print(f"   Generating general summary across {len(all_analyses)} categories...")

        # Extract relevant fields from each analysis
        category_analyses = []
        for analysis in all_analyses:
            category_analyses.append({
                "category": analysis.get("category", "Unknown"),
                "key_differences": analysis.get("key_differences", ""),
                "critical_thinking": analysis.get("critical_thinking", ""),
                "best_coverage": analysis.get("best_coverage", ""),
                "salesperson_talking_points": analysis.get("salesperson_talking_points", []),
                "objective_assessment": analysis.get("objective_assessment", {}),
            })

        prompt = create_summary_prompt(
            category_analyses=category_analyses,
            language=self.language,
        )

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "summary_generation",
                "category_count": len(all_analyses),
                "model": self.model_name,
                "language": self.language,
            }
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=4096,
            temperature=0.4,
            response_mime_type="application/json",
            response_schema=ComparisonSummary.model_json_schema(),
        )

        try:
            summary = json.loads(response)

            # Update trace with results
            langfuse.update_current_trace(
                metadata={
                    "summary_generated": True,
                    "overall_winner": summary.get("objective_evaluation", {}).get("overall_winner"),
                }
            )

            return summary
        except json.JSONDecodeError as e:
            print(f"    ✗ Failed to parse summary JSON: {e}")
            langfuse.update_current_trace(metadata={"success": False, "error": str(e)})

            # Return minimal summary
            return {
                "key_differences": "",
                "category_strengths": [],
                "probtp_overall_strengths": [],
                "axa_overall_strengths": [],
                "objective_evaluation": {
                    "overall_winner": "unknown",
                    "confidence": "low",
                    "reasoning": "Failed to generate summary",
                },
                "category_winners": [],
                "selling_points": [],
                "target_customer_fit": "",
            }

    @observe(name="generate_recommendation")
    async def _generate_recommendation(
        self,
        all_analyses: list[dict[str, Any]],
    ) -> str:
        """Generate overall recommendation from all category analyses."""
        print("   Generating overall recommendation...")

        # Extract talking points from all analyses
        talking_points = []
        for analysis in all_analyses:
            if "salesperson_talking_points" in analysis:
                talking_points.extend(analysis["salesperson_talking_points"])

        talking_points_text = "\n".join([f"- {tp}" for tp in talking_points])

        prompt = f"""You are an expert insurance analyst. Based on the category analyses, write an overall recommendation section.

**Language:** Write in {self.language}.

**Structure:**
1. Strengths & Weaknesses Summary (bullet points for each contract)
2. Decision Factors (key questions a salesperson should ask the customer)
3. Final Guidance (2-3 paragraphs)

**Talking Points from Analyses:**

{talking_points_text}

**Output:** Return ONLY the recommendation section in {self.language}. No JSON, no preamble."""

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "recommendation_generation",
                "talking_points_count": len(talking_points),
                "model": self.model_name,
                "language": self.language,
            }
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=2048,
            temperature=0.4,
            response_mime_type="text/plain",
        )

        langfuse.update_current_trace(
            metadata={
                "recommendation_generated": True,
                "recommendation_length": len(response),
            }
        )

        return response

    def _save_checkpoint(self, name: str, data: dict[str, Any] | str) -> None:
        """Save checkpoint to tmp directory."""
        checkpoint_path = self.tmp_dir / f"{name}.json"
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_checkpoint(self, name: str) -> dict[str, Any] | str:
        """Load checkpoint from tmp directory."""
        checkpoint_path = self.tmp_dir / f"{name}.json"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        with open(checkpoint_path, encoding="utf-8") as f:
            return json.load(f)


async def main():
    """Example usage of taxonomy-first pipeline."""
    # Paths (matching two_phase_pipeline)
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    probtp_path = output_base / "File #3 - Panorama FMC 2025.json"
    axa_path = (
        output_base
        / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"
    )
    output_dir = Path(__file__).parent.parent / "output" / "taxonomy_first"

    # Check if documents exist
    if not probtp_path.exists():
        print(f"Error: ProBTP document not found: {probtp_path}")
        return

    if not axa_path.exists():
        print(f"Error: AXA document not found: {axa_path}")
        return

    # Create pipeline
    pipeline = TaxonomyFirstPipeline(
        probtp_doc_path=probtp_path,
        axa_doc_path=axa_path,
        output_dir=output_dir,
        model_name="gemini-2.5-flash",
        categories_to_process=None # ALL # ["hospitalisation", "optique"],  # Test with 2 categories
    )

    # Run pipeline
    results = await pipeline.run(
        probtp_levels=["S4", "P5"],
        axa_levels=["Base obligatoire"],
        skip_taxonomy=False,
        skip_extraction=False,
        skip_assembly=False,
        skip_analysis=False,
        skip_summary=False,
        skip_recommendation=False
    )

    print("\n✅ Pipeline complete!")
    print(f"   Output directory: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
