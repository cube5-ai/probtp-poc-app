"""Policy Levels Recommendation Pipeline for Insurance Contract Comparison.

This pipeline recommends the best vendor A (reference) level combination to compete with a vendor B level:
1. Extract universal taxonomy from vendor A
2. Extract values for ALL vendor A levels + single vendor B level per category
3. Build multi-level comparison documents
4. Generate category-level recommendations (best vendor A level per category)
5. Generate global recommendation (select S + P level combination)
6. Assemble final report

Key differences from taxonomy_first_pipeline:
- Extracts ALL vendor A levels at once (e.g., S1-S5, P1-P5)
- Uses simplified value schema (base_value + detailed_value)
- Adds recommendation phases (category + global)
- Focus on selling arguments and competitive positioning
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

# Category to level type mapping (S = Soins, P = Prévoyance)
CATEGORY_LEVEL_MAPPING = {
    "Soins courants": "S",
    "Hospitalisation": "S",
    "Optique": "P",
    "Dentaire": "P",
    "Soins Dentaires": "P",
    "Aides auditives": "P",
    "Audiologie": "P",
    "Prestations complémentaires": "P",
    "Prestations Complémentaires": "P",
}

from prompts.policy_recommendation.category_recommendation_prompt import (
    CategoryRecommendation,
    create_category_recommendation_prompt,
)
from prompts.policy_recommendation.global_recommendation_prompt import (
    GlobalRecommendation,
    create_global_recommendation_prompt,
)
from prompts.policy_recommendation.value_extraction_multi_level_prompt import (
    CategoryValueExtractionMultiLevel,
    create_value_extraction_multi_level_prompt,
)
from prompts.taxonomy_first.taxonomy_extraction_prompt import (
    ExtractionMetadata,
    ProBTPTaxonomy,
    create_taxonomy_extraction_prompt,
)
from utils.document_loader import ParsedDocument
from utils.gemini_client import generate_with_reasoning
from utils.multi_level_comparison_builder import (
    MultiLevelComparisonDocument,
    build_multi_level_comparison_document,
)
from utils.recommendation_report_formatter import build_recommendation_report
from utils.report_formatter import create_report_metadata, save_report


def extract_leaves_from_flat_taxonomy(
    nodes: list[dict[str, Any]], parent_id: str | None = None
) -> list[dict[str, Any]]:
    """Extract all leaf nodes that are descendants of a given parent from a flat taxonomy."""
    leaves = []

    if parent_id is not None:
        descendants = get_descendants(nodes, parent_id)
        candidate_nodes = descendants
    else:
        candidate_nodes = nodes

    for node in candidate_nodes:
        if node.get("is_leaf", False):
            leaves.append({
                "path": node["path"],
                "leaf_id": node["node_id"],
                "description": node["description"],
                "securite_sociale_coverage": node.get("securite_sociale_coverage"),
            })

    return leaves


def get_descendants(nodes: list[dict[str, Any]], parent_id: str) -> list[dict[str, Any]]:
    """Get all descendant nodes of a given parent from a flat list."""
    descendant_ids = set()
    nodes_by_id = {node["node_id"]: node for node in nodes}

    queue = [parent_id]
    while queue:
        current_id = queue.pop(0)
        for node in nodes:
            node_id = node["node_id"]
            if node.get("parent_id") == current_id and node_id not in descendant_ids:
                descendant_ids.add(node_id)
                queue.append(node_id)

    descendants = [node for node in nodes if node["node_id"] in descendant_ids]
    return descendants


def filter_levels_for_category(category_name: str, all_levels: list[str] | None) -> list[str] | None:
    """Filter levels appropriate for a category (S or P)."""
    if not all_levels:
        return None

    level_type = CATEGORY_LEVEL_MAPPING.get(category_name)

    if not level_type:
        return all_levels

    filtered_levels = [level for level in all_levels if level.startswith(level_type)]

    return filtered_levels if filtered_levels else None


class PolicyRecommendationPipeline:
    """Policy levels recommendation pipeline.

    Workflow:
    1. Extract taxonomy from vendor A (reference)
    2. Extract values for ALL vendor A levels + single vendor B level per category
    3. Build multi-level comparison documents
    4. Generate category recommendations (best vendor A level per category)
    5. Generate global recommendation (select S + P combination)
    6. Assemble final report
    """

    def __init__(
        self,
        vendor_a_ref_doc_path: str | Path,
        vendor_b_doc_path: str | Path,
        vendor_a_ref_name: str,
        vendor_b_name: str,
        vendor_b_target_level: str,
        output_dir: str | Path,
        model_name: str = "gemini-2.5-pro",
        categories_to_process: list[str] | None = None,
        language: str = "French (France)",
        vendor_b_all_levels: list[str] | None = None,
    ):
        """Initialize pipeline.

        Args:
            vendor_a_ref_doc_path: Path to vendor A parsed document JSON
            vendor_b_doc_path: Path to vendor B parsed document JSON
            vendor_a_ref_name: Vendor A name (e.g., "ProBTP")
            vendor_b_name: Vendor B name (e.g., "AXA")
            vendor_b_target_level: Vendor B level to compete against (e.g., "Base obligatoire")
            output_dir: Output directory
            model_name: Model name (default: gemini-2.5-pro)
            categories_to_process: Categories to process (None = all)
            language: Output language
            vendor_b_all_levels: All vendor B levels to extract (None = infer from target level)
        """
        self.vendor_a_ref_doc_path = Path(vendor_a_ref_doc_path)
        self.vendor_b_doc_path = Path(vendor_b_doc_path)
        self.vendor_a_ref_name = vendor_a_ref_name
        self.vendor_b_name = vendor_b_name
        self.vendor_b_target_level = vendor_b_target_level
        self.vendor_b_all_levels = vendor_b_all_levels
        self.model_name = model_name
        self.categories_to_process = categories_to_process
        self.language = language

        # Create output directory
        vendor_folder_name = f"{vendor_a_ref_name}_vs_{vendor_b_name}"
        self.output_dir = Path(output_dir) / vendor_folder_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.output_dir / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

        # Load documents
        print("Loading documents...")
        self.vendor_a_ref_doc = ParsedDocument(self.vendor_a_ref_doc_path)
        self.vendor_b_doc = ParsedDocument(self.vendor_b_doc_path)

        # Pipeline state
        self.taxonomy: dict[str, Any] | None = None
        self.extractions: dict[str, dict[str, Any]] = {}  # category_id -> {vendor_a_ref, vendor_b}
        self.comparison_documents: dict[str, dict[str, Any]] = {}  # category_id -> ComparisonDocument
        self.category_recommendations: dict[str, dict[str, Any]] = {}  # category_id -> CategoryRecommendation
        self.global_recommendation: dict[str, Any] | None = None

    @observe(name="policy_recommendation_pipeline")
    async def run(
        self,
        vendor_a_ref_all_levels: list[str],
        skip_taxonomy: bool = False,
        skip_extraction: bool = False,
        skip_assembly: bool = False,
        skip_category_recommendations: bool = False,
        skip_global_recommendation: bool = False,
    ) -> dict[str, Any]:
        """Run the complete pipeline.

        Args:
            vendor_a_ref_all_levels: ALL vendor A levels to extract (e.g., ['S1', 'S2', ..., 'P1', 'P2', ...])
            skip_taxonomy: Skip taxonomy extraction
            skip_extraction: Skip value extraction
            skip_assembly: Skip comparison document assembly
            skip_category_recommendations: Skip category recommendations
            skip_global_recommendation: Skip global recommendation

        Returns:
            Pipeline results dict
        """
        langfuse.update_current_trace(
            name="policy_recommendation_pipeline",
            metadata={
                "pipeline_type": "policy_recommendation",
                "vendor_a_ref_name": self.vendor_a_ref_name,
                "vendor_b_name": self.vendor_b_name,
                "vendor_b_target_level": self.vendor_b_target_level,
                "vendor_a_ref_all_levels": vendor_a_ref_all_levels,
            },
        )

        print(f"\n{'=' * 80}")
        print("POLICY LEVELS RECOMMENDATION PIPELINE")
        print(f"{'=' * 80}")
        print(f"Vendor A (Reference): {self.vendor_a_ref_name}")
        print(f"Vendor B: {self.vendor_b_name} - Level: {self.vendor_b_target_level}")
        print(f"Vendor A levels: {vendor_a_ref_all_levels}")
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
            print("\n⏩ Loading taxonomy from checkpoint")
            self.taxonomy = self._load_checkpoint("taxonomy")

        all_nodes = self.taxonomy["nodes"]
        top_level_categories = [
            node for node in all_nodes if node.get("parent_id") == "_root_"
        ]

        if self.categories_to_process:
            categories = [
                cat for cat in top_level_categories
                if cat["name"] in self.categories_to_process
            ]
        else:
            categories = top_level_categories

        print(f"\n📋 Processing {len(categories)} categories: {[c['name'] for c in categories]}")

        # Phase 2: Extract values (multi-level for vendor A, single level for vendor B)
        if not skip_extraction:
            print(f"\n{'─' * 80}")
            print("PHASE 2: Value Extraction")
            print(f"{'─' * 80}")

            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]
                category_leaves = extract_leaves_from_flat_taxonomy(all_nodes, category_id)

                print(f"\n📦 Category: {category_name} ({category_id})")

                # Filter vendor A levels relevant to this category
                category_vendor_a_levels = filter_levels_for_category(category_name, vendor_a_ref_all_levels)
                print(f"   → Vendor A levels for this category: {category_vendor_a_levels}")

                # Extract vendor A multi-level values
                checkpoint_name = f"{category_id}_vendor_a_ref_multi_level_values"
                checkpoint_path = self.tmp_dir / f"{checkpoint_name}.json"

                if checkpoint_path.exists():
                    print("   ⏩ Vendor A: Loading from checkpoint")
                    vendor_a_extraction = self._load_checkpoint(checkpoint_name)
                else:
                    vendor_a_extraction = await self._extract_values_multi_level(
                        vendor=self.vendor_a_ref_name,
                        vendor_doc=self.vendor_a_ref_doc,
                        category_id=category_id,
                        category_name=category_name,
                        category_leaves=category_leaves,
                        policy_levels=category_vendor_a_levels,
                        full_taxonomy_nodes=all_nodes,
                    )
                    self._save_checkpoint(checkpoint_name, vendor_a_extraction)
                    print(f"   ✓ Vendor A: {len(vendor_a_extraction['extracted_values'])} leaves")

                # Extract vendor B multi-level values (all levels, no filtering)
                checkpoint_name = f"{category_id}_vendor_b_multi_level_values"
                checkpoint_path = self.tmp_dir / f"{checkpoint_name}.json"

                if checkpoint_path.exists():
                    print("   ⏩ Vendor B: Loading from checkpoint")
                    vendor_b_extraction = self._load_checkpoint(checkpoint_name)
                else:
                    # Extract ALL vendor B levels (no category filtering)
                    if self.vendor_b_all_levels:
                        print(f"   → Vendor B levels: {self.vendor_b_all_levels}")
                        vendor_b_extraction = await self._extract_values_multi_level(
                            vendor=self.vendor_b_name,
                            vendor_doc=self.vendor_b_doc,
                            category_id=category_id,
                            category_name=category_name,
                            category_leaves=category_leaves,
                            policy_levels=self.vendor_b_all_levels,
                            full_taxonomy_nodes=all_nodes,
                        )
                    else:
                        # Fallback: extract only target level if vendor_b_all_levels not provided
                        print(f"   → Vendor B level: {self.vendor_b_target_level} (single level)")
                        vendor_b_extraction = await self._extract_values_multi_level(
                            vendor=self.vendor_b_name,
                            vendor_doc=self.vendor_b_doc,
                            category_id=category_id,
                            category_name=category_name,
                            category_leaves=category_leaves,
                            policy_levels=[self.vendor_b_target_level],
                            full_taxonomy_nodes=all_nodes,
                        )
                    self._save_checkpoint(checkpoint_name, vendor_b_extraction)
                    print(f"   ✓ Vendor B: {len(vendor_b_extraction['extracted_values'])} leaves")

                self.extractions[category_id] = {
                    "vendor_a_ref": vendor_a_extraction,
                    "vendor_b": vendor_b_extraction,
                }
        else:
            print("\n⏩ Skipping value extraction (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                vendor_a_extraction = self._load_checkpoint(f"{category_id}_vendor_a_ref_multi_level_values")
                vendor_b_extraction = self._load_checkpoint(f"{category_id}_vendor_b_multi_level_values")
                self.extractions[category_id] = {
                    "vendor_a_ref": vendor_a_extraction,
                    "vendor_b": vendor_b_extraction,
                }

        # Phase 3: Build multi-level comparison documents
        if not skip_assembly:
            print(f"\n{'─' * 80}")
            print("PHASE 3: Multi-Level Comparison Document Building")
            print(f"{'─' * 80}")

            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n🔧 Building comparison document: {category_name}")

                category_leaves = extract_leaves_from_flat_taxonomy(all_nodes, category_id)
                category_with_leaves = {
                    **category,
                    "leaves": category_leaves,
                    "category_name": category_name,
                }

                comparison_doc = build_multi_level_comparison_document(
                    category_taxonomy=category_with_leaves,
                    vendor_a_ref_multi_level_extraction=self.extractions[category_id]["vendor_a_ref"],
                    vendor_b_multi_level_extraction=self.extractions[category_id]["vendor_b"],
                    vendor_b_target_level=self.vendor_b_target_level,
                    vendor_a_ref_name=self.vendor_a_ref_name,
                    vendor_b_name=self.vendor_b_name,
                )

                self.comparison_documents[category_id] = comparison_doc.model_dump()
                self._save_checkpoint(f"{category_id}_comparison_document", comparison_doc.model_dump())

                print(f"   ✓ Leaves: {len(comparison_doc.leaves)}")
        else:
            print("\n⏩ Skipping comparison document building (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                comparison_doc = self._load_checkpoint(f"{category_id}_comparison_document")
                self.comparison_documents[category_id] = comparison_doc

        # Phase 4: Generate category recommendations
        if not skip_category_recommendations:
            print(f"\n{'─' * 80}")
            print("PHASE 4: Category Recommendations")
            print(f"{'─' * 80}")

            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n💡 Generating recommendation: {category_name}")

                category_rec = await self._generate_category_recommendation(
                    category_name=category_name,
                    comparison_document=self.comparison_documents[category_id],
                )

                self.category_recommendations[category_id] = category_rec
                self._save_checkpoint(f"{category_id}_recommendation", category_rec)

                print(f"   ✓ Recommended level: {category_rec.get('recommended_vendor_a_ref_level')}")
        else:
            print("\n⏩ Skipping category recommendations (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                category_rec = self._load_checkpoint(f"{category_id}_recommendation")
                self.category_recommendations[category_id] = category_rec

        # Phase 5: Generate global recommendation
        if not skip_global_recommendation:
            print(f"\n{'─' * 80}")
            print("PHASE 5: Global Recommendation")
            print(f"{'─' * 80}")

            self.global_recommendation = await self._generate_global_recommendation(
                category_recommendations=list(self.category_recommendations.values()),
            )
            self._save_checkpoint("global_recommendation", self.global_recommendation)

            s_level = self.global_recommendation.get("recommended_s_level")
            p_level = self.global_recommendation.get("recommended_p_level")
            print(f"   ✓ Recommended combination: {s_level} + {p_level}")
        else:
            print("\n⏩ Skipping global recommendation (loading from checkpoint)")
            self.global_recommendation = self._load_checkpoint("global_recommendation")

        # Phase 6: Assemble final report
        print(f"\n{'─' * 80}")
        print("PHASE 6: Final Report Assembly")
        print(f"{'─' * 80}")

        s_level = self.global_recommendation.get("recommended_s_level", "SX")
        p_level = self.global_recommendation.get("recommended_p_level", "PY")

        final_report_path = (
            self.output_dir
            / f"recommendation_report_{self.vendor_a_ref_name}_{s_level}_{p_level}_vs_{self.vendor_b_name}_{self.vendor_b_target_level.replace(' ', '_')}.md"
        )

        metadata = create_report_metadata(
            vendor_a_ref_doc_name=self.vendor_a_ref_doc.name,
            vendor_b_doc_name=self.vendor_b_doc.name,
            vendor_a_ref_name=self.vendor_a_ref_name,
            vendor_b_name=self.vendor_b_name,
            vendor_a_ref_levels=[f"{s_level}+{p_level}"],
            vendor_b_levels=[self.vendor_b_target_level],
            model=self.model_name,
            categories=[cat["name"] for cat in categories],
        )

        report = build_recommendation_report(
            global_recommendation=self.global_recommendation,
            category_recommendations=list(self.category_recommendations.values()),
            metadata=metadata,
        )

        save_report(report, final_report_path)
        print(f"   ✓ Final report saved: {final_report_path.name}")

        # Save JSON output
        json_output_path = final_report_path.with_suffix(".json")
        json_data = {
            "metadata": metadata,
            "taxonomy": self.taxonomy,
            "extractions": self.extractions,
            "comparison_documents": self.comparison_documents,
            "category_recommendations": self.category_recommendations,
            "global_recommendation": self.global_recommendation,
        }

        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"   ✓ JSON output saved: {json_output_path.name}")

        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"Recommended combination: {s_level} + {p_level}")
        print(f"Final report: {final_report_path}")
        print(f"{'=' * 80}\n")

        return {
            "taxonomy": self.taxonomy,
            "extractions": self.extractions,
            "comparison_documents": self.comparison_documents,
            "category_recommendations": self.category_recommendations,
            "global_recommendation": self.global_recommendation,
            "final_report_path": str(final_report_path),
            "json_output_path": str(json_output_path),
        }

    @observe(name="extract_taxonomy")
    async def _extract_taxonomy(self) -> dict[str, Any]:
        """Extract taxonomy from vendor A document."""
        print(f"Extracting taxonomy from {self.vendor_a_ref_name} document...")

        vendor_a_markdown = self.vendor_a_ref_doc.get_full_markdown()
        prompt = create_taxonomy_extraction_prompt(vendor_a_markdown)

        response = await generate_with_reasoning(
            prompt=prompt,
            model="gemini-2.5-pro",
            thinking_budget=4096,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ProBTPTaxonomy.model_json_schema(),
            use_vertex=False,
        )

        taxonomy = json.loads(response)

        metadata = ExtractionMetadata(
            source_document=self.vendor_a_ref_doc.name,
            extraction_date=datetime.now().isoformat(),
            extraction_approach="flat_depth_first",
            extractor_model=self.model_name,
        )

        taxonomy["metadata"] = metadata

        all_nodes = taxonomy["nodes"]
        top_level_categories = [node for node in all_nodes if node.get("parent_id") == "_root_"]

        print(f"   ✓ Extracted {len(top_level_categories)} top-level categories ({len(all_nodes)} total nodes)")

        return taxonomy

    @observe(name="extract_values_multi_level")
    async def _extract_values_multi_level(
        self,
        vendor: str,
        vendor_doc: ParsedDocument,
        category_id: str,
        category_name: str,
        category_leaves: list[dict[str, Any]],
        policy_levels: list[str] | None,
        full_taxonomy_nodes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Extract values for multiple policy levels."""
        print(f"   Extracting {vendor} values for {category_name} (levels: {policy_levels})...")

        vendor_markdown = vendor_doc.get_markdown_with_expanded_tables()
        prompt = create_value_extraction_multi_level_prompt(
            vendor=vendor,
            vendor_markdown=vendor_markdown,
            category_id=category_id,
            category_name=category_name,
            policy_levels=policy_levels or ["default"],
            taxonomy_leaves=category_leaves,
            full_taxonomy_nodes=full_taxonomy_nodes,
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=2048,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=CategoryValueExtractionMultiLevel.model_json_schema(),
            use_vertex=False,
        )

        extraction = json.loads(response)
        extraction["vendor_name"] = vendor

        return extraction


    @observe(name="generate_category_recommendation")
    async def _generate_category_recommendation(
        self,
        category_name: str,
        comparison_document: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate category-level recommendation."""
        prompt = create_category_recommendation_prompt(
            comparison_document=comparison_document,
            vendor_a_ref_name=self.vendor_a_ref_name,
            vendor_b_name=self.vendor_b_name,
            language=self.language,
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=4096,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=CategoryRecommendation.model_json_schema(),
            use_vertex=False,
        )

        recommendation = json.loads(response)
        return recommendation

    @observe(name="generate_global_recommendation")
    async def _generate_global_recommendation(
        self,
        category_recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate global recommendation (S + P level combination)."""
        print("   Generating global recommendation...")

        prompt = create_global_recommendation_prompt(
            category_recommendations=category_recommendations,
            vendor_a_ref_name=self.vendor_a_ref_name,
            vendor_b_name=self.vendor_b_name,
            vendor_b_level=self.vendor_b_target_level,
            language=self.language,
        )

        response = await generate_with_reasoning(
            prompt=prompt,
            model=self.model_name,
            thinking_budget=4096,
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=GlobalRecommendation.model_json_schema(),
            use_vertex=False,
        )

        recommendation = json.loads(response)
        return recommendation

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
    """Example usage of policy recommendation pipeline."""
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    # ProBTP vs AXA example
    vendor_a_ref_path = output_base / "File #2 - Laurent M - tableau garantie fm 2025 word.json"
    vendor_b_path = output_base / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"
    output_dir = Path(__file__).parent.parent / "output" / "policy_recommendation"

    # Check if documents exist
    if not vendor_a_ref_path.exists():
        print(f"Error: Vendor A document not found: {vendor_a_ref_path}")
        return

    if not vendor_b_path.exists():
        print(f"Error: Vendor B document not found: {vendor_b_path}")
        return

    # Create pipeline
    pipeline = PolicyRecommendationPipeline(
        vendor_a_ref_doc_path=vendor_a_ref_path,
        vendor_b_doc_path=vendor_b_path,
        vendor_a_ref_name="ProBTP",
        vendor_b_name="AXA",
        vendor_b_target_level="Base obligatoire",
        output_dir=output_dir,
        model_name="gemini-2.5-pro",
        categories_to_process=["Hospitalisation", "Dentaire"],  # Test with one category first
        vendor_b_all_levels=["Complémentaire responsable base obligatoire", "Option 1"],  # Extract all AXA levels
    )

    # Run pipeline with ALL ProBTP levels
    results = await pipeline.run(
        vendor_a_ref_all_levels=["S1", "S2", "S3", "S3+", "S4", "S5/S6", "P1", "P2", "P3", "P3+", "P4", "P5", "P6"],
        skip_taxonomy=True,
        skip_extraction=True,
        skip_assembly=True,
        skip_category_recommendations=False,  # Regenerate with new schema
        skip_global_recommendation=False,
    )

    print("\n✅ Pipeline complete!")
    print(f"   Output directory: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
