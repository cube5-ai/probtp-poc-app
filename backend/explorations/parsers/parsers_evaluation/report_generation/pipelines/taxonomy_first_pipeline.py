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

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch
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

from prompts.taxonomy_extraction_prompt import (
    ProBTPTaxonomy,
    create_taxonomy_extraction_prompt,
)
from prompts.value_extraction_prompt import (
    CategoryValueExtraction,
    create_value_extraction_prompt,
)
from prompts.analysis_prompt import (
    AnalysisOutput,
    create_analysis_prompt,
)
from utils.document_loader import ParsedDocument
from utils.taxonomy_assembler import (
    assemble_comparison_table,
    validate_assembled_table,
)
from utils.markdown_generator import (
    generate_comparison_markdown,
)


def extract_leaves_from_flat_taxonomy(
    nodes: list[dict[str, Any]],
    parent_id: str | None = None
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
            leaves.append({
                "path": node["path"],
                "leaf_id": node["node_id"],
                "description": node["description"],
                "basis": node.get("basis"),
            })

    return leaves


def get_descendants(nodes: list[dict[str, Any]], parent_id: str) -> list[dict[str, Any]]:
    """
    Get all descendant nodes of a given parent from a flat list.

    Args:
        nodes: Flat list of all taxonomy nodes
        parent_id: Parent node ID

    Returns:
        List of all descendants (including direct children and their descendants)
    """
    descendants = []
    nodes_by_id = {node["node_id"]: node for node in nodes}

    # BFS to find all descendants
    queue = [parent_id]
    while queue:
        current_id = queue.pop(0)
        # Find direct children
        for node in nodes:
            if node.get("parent_id") == current_id:
                descendants.append(node)
                queue.append(node["node_id"])

    return descendants


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
        """
        self.probtp_doc_path = Path(probtp_doc_path)
        self.axa_doc_path = Path(axa_doc_path)
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.categories_to_process = categories_to_process

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.output_dir / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)

        # Load documents
        print(f"Loading documents...")
        self.probtp_doc = ParsedDocument(self.probtp_doc_path)
        self.axa_doc = ParsedDocument(self.axa_doc_path)

        # Initialize GenAI client (Vertex AI)
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID", "probtp-poc-prod"),
            location="global",
        )

        # Pipeline state
        self.taxonomy: dict[str, Any] | None = None
        self.extractions: dict[str, dict[str, Any]] = {}  # category_id -> {probtp: ..., axa: ...}
        self.comparison_tables: dict[str, dict[str, Any]] = {}  # category_id -> ComparisonTable
        self.analyses: dict[str, dict[str, Any]] = {}  # category_id -> Analysis

    @observe(name="taxonomy_first_pipeline")
    def run(
        self,
        probtp_level: str = "P4",
        axa_level: str = "Base Obligatoire",
        skip_taxonomy: bool = False,
        skip_extraction: bool = False,
        skip_assembly: bool = False,
        skip_analysis: bool = False,
    ) -> dict[str, Any]:
        """
        Run the complete pipeline.

        Args:
            probtp_level: ProBTP policy level to extract
            axa_level: AXA policy level to extract
            skip_taxonomy: Skip taxonomy extraction (load from checkpoint)
            skip_extraction: Skip value extraction (load from checkpoint)
            skip_assembly: Skip table assembly (load from checkpoint)
            skip_analysis: Skip analysis generation (load from checkpoint)

        Returns:
            Pipeline results dict
        """
        # Initialize Langfuse trace for entire pipeline
        langfuse.update_current_trace(
            name="taxonomy_first_pipeline",
            metadata={
                "pipeline_type": "taxonomy_first",
                "probtp_document": self.probtp_doc.name,
                "axa_document": self.axa_doc.name,
                "probtp_level": probtp_level,
                "axa_level": axa_level,
                "categories_to_process": self.categories_to_process,
                "skip_taxonomy": skip_taxonomy,
                "skip_extraction": skip_extraction,
                "skip_assembly": skip_assembly,
                "skip_analysis": skip_analysis,
            }
        )
        print(f"\n{'='*80}")
        print(f"TAXONOMY-FIRST PIPELINE")
        print(f"{'='*80}")
        print(f"ProBTP document: {self.probtp_doc.name}")
        print(f"AXA document: {self.axa_doc.name}")
        print(f"ProBTP level: {probtp_level}")
        print(f"AXA level: {axa_level}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*80}\n")

        # Phase 1: Extract taxonomy
        if not skip_taxonomy:
            print(f"\n{'─'*80}")
            print(f"PHASE 1: Taxonomy Extraction")
            print(f"{'─'*80}")
            self.taxonomy = self._extract_taxonomy()
            self._save_checkpoint("taxonomy", self.taxonomy)
        else:
            print(f"\n⏩ Skipping taxonomy extraction (loading from checkpoint)")
            self.taxonomy = self._load_checkpoint("taxonomy")

        # Filter top-level categories if specified
        all_nodes = self.taxonomy["nodes"]
        top_level_categories = [node for node in all_nodes if node.get("parent_id") is None]

        if self.categories_to_process:
            categories = [
                cat for cat in top_level_categories
                if cat["node_id"] in self.categories_to_process
            ]
            print(f"\n📋 Processing {len(categories)} categories: {[c['node_id'] for c in categories]}")
        else:
            categories = top_level_categories
            print(f"\n📋 Processing all {len(categories)} categories")

        # Phase 2: Extract values per category
        if not skip_extraction:
            print(f"\n{'─'*80}")
            print(f"PHASE 2: Value Extraction")
            print(f"{'─'*80}")
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                # Extract leaves from flat taxonomy for this category
                category_leaves = extract_leaves_from_flat_taxonomy(all_nodes, category_id)

                print(f"\n📦 Category: {category_name} ({category_id})")
                print(f"   Leaves: {len(category_leaves)}")

                # Extract ProBTP values
                probtp_extraction = self._extract_values(
                    vendor="ProBTP",
                    vendor_doc=self.probtp_doc,
                    category_id=category_id,
                    category_name=category_name,
                    category_leaves=category_leaves,
                    policy_level=probtp_level,
                )
                self._save_checkpoint(f"{category_id}_probtp_values", probtp_extraction)

                # Extract AXA values
                axa_extraction = self._extract_values(
                    vendor="AXA",
                    vendor_doc=self.axa_doc,
                    category_id=category_id,
                    category_name=category_name,
                    category_leaves=category_leaves,
                    policy_level=axa_level,
                )
                self._save_checkpoint(f"{category_id}_axa_values", axa_extraction)

                self.extractions[category_id] = {
                    "probtp": probtp_extraction,
                    "axa": axa_extraction,
                }

                print(f"   ✓ ProBTP values: {len(probtp_extraction['extracted_values'])} leaves")
                print(f"   ✓ AXA values: {len(axa_extraction['extracted_values'])} leaves")
        else:
            print(f"\n⏩ Skipping value extraction (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                probtp_extraction = self._load_checkpoint(f"{category_id}_probtp_values")
                axa_extraction = self._load_checkpoint(f"{category_id}_axa_values")
                self.extractions[category_id] = {
                    "probtp": probtp_extraction,
                    "axa": axa_extraction,
                }

        # Phase 3: Assemble comparison tables
        if not skip_assembly:
            print(f"\n{'─'*80}")
            print(f"PHASE 3: Table Assembly")
            print(f"{'─'*80}")
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n🔧 Assembling: {category_name}")

                # Extract leaves for this category to pass to assembler
                category_leaves = extract_leaves_from_flat_taxonomy(all_nodes, category_id)

                # Create category dict with leaves for assembler
                category_with_leaves = {**category, "leaves": category_leaves}

                comparison_table = assemble_comparison_table(
                    taxonomy_category=category_with_leaves,
                    probtp_extraction=self.extractions[category_id]["probtp"],
                    axa_extraction=self.extractions[category_id]["axa"],
                )

                # Validate
                is_valid, errors = validate_assembled_table(comparison_table)
                if not is_valid:
                    print(f"   ⚠️  Validation errors:")
                    for error in errors:
                        print(f"      - {error}")
                else:
                    print(f"   ✓ Table structure valid")

                self.comparison_tables[category_id] = comparison_table
                self._save_checkpoint(f"{category_id}_comparison_table", comparison_table)

                print(f"   ✓ Rows: {len(comparison_table['rows'])}")
                print(f"   ✓ Columns: {comparison_table['metadata']['total_columns']}")
        else:
            print(f"\n⏩ Skipping table assembly (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                comparison_table = self._load_checkpoint(f"{category_id}_comparison_table")
                self.comparison_tables[category_id] = comparison_table

        # Phase 4: Generate analysis
        if not skip_analysis:
            print(f"\n{'─'*80}")
            print(f"PHASE 4: Analysis Generation")
            print(f"{'─'*80}")
            for category in categories:
                category_id = category["node_id"]
                category_name = category["name"]

                print(f"\n📊 Analyzing: {category_name}")

                analysis = self._generate_analysis(
                    category_name=category_name,
                    comparison_table=self.comparison_tables[category_id],
                )

                self.analyses[category_id] = analysis
                self._save_checkpoint(f"{category_id}_analysis", analysis)

                print(f"   ✓ Analysis complete")
        else:
            print(f"\n⏩ Skipping analysis (loading from checkpoints)")
            for category in categories:
                category_id = category["node_id"]
                analysis = self._load_checkpoint(f"{category_id}_analysis")
                self.analyses[category_id] = analysis

        # Phase 5: Generate reports
        print(f"\n{'─'*80}")
        print(f"PHASE 5: Report Generation")
        print(f"{'─'*80}")

        for category in categories:
            category_id = category["node_id"]
            category_name = category["name"]

            print(f"\n📝 Generating report: {category_name}")

            # Generate markdown
            markdown = generate_comparison_markdown(
                comparison_table=self.comparison_tables[category_id],
                analysis=self.analyses[category_id],
            )

            # Save markdown
            markdown_path = self.output_dir / f"{category_id}_comparison.md"
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

            print(f"   ✓ Markdown saved: {markdown_path.name}")

        # Generate summary
        print(f"\n{'='*80}")
        print(f"PIPELINE COMPLETE")
        print(f"{'='*80}")
        print(f"Categories processed: {len(categories)}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*80}\n")

        return {
            "taxonomy": self.taxonomy,
            "extractions": self.extractions,
            "comparison_tables": self.comparison_tables,
            "analyses": self.analyses,
        }

    @observe(name="extract_taxonomy")
    def _extract_taxonomy(self) -> dict[str, Any]:
        """Extract ProBTP taxonomy."""
        print(f"Extracting taxonomy from ProBTP document...")

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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProBTPTaxonomy,
            ),
        )

        taxonomy = json.loads(response.text)

        all_nodes = taxonomy["nodes"]
        top_level_categories = [node for node in all_nodes if node.get("parent_id") is None]

        print(f"   ✓ Extracted {len(top_level_categories)} top-level categories ({len(all_nodes)} total nodes)")

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
    def _extract_values(
        self,
        vendor: str,
        vendor_doc: ParsedDocument,
        category_id: str,
        category_name: str,
        category_leaves: list[dict[str, Any]],
        policy_level: str,
    ) -> dict[str, Any]:
        """Extract values for a category from vendor document."""
        print(f"   Extracting {vendor} values for {category_name}...")

        vendor_markdown = vendor_doc.get_full_markdown()
        prompt = create_value_extraction_prompt(
            vendor=vendor,
            vendor_markdown=vendor_markdown,
            category_id=category_id,
            category_name=category_name,
            policy_level=policy_level,
            taxonomy_leaves=category_leaves,
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
                "policy_level": policy_level,
                "taxonomy_leaves_count": len(category_leaves),
                "model": self.model_name,
            }
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CategoryValueExtraction,
            ),
        )

        extraction = json.loads(response.text)

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
    def _generate_analysis(
        self,
        category_name: str,
        comparison_table: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate analysis for comparison table."""
        prompt = create_analysis_prompt(
            comparison_table=comparison_table,
        )

        print(f"      Model: {self.model_name}")

        # Update Langfuse trace metadata
        langfuse.update_current_trace(
            metadata={
                "phase": "analysis_generation",
                "category": category_name,
                "model": self.model_name,
                "table_rows": len(comparison_table.get("rows", [])),
            }
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalysisOutput,
            ),
        )

        analysis = json.loads(response.text)

        # Update trace with results
        langfuse.update_current_trace(
            metadata={
                "analysis_generated": True,
                "has_key_differences": "key_differences" in analysis,
            }
        )

        return analysis

    def _save_checkpoint(self, name: str, data: dict[str, Any]) -> None:
        """Save checkpoint to tmp directory."""
        checkpoint_path = self.tmp_dir / f"{name}.json"
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_checkpoint(self, name: str) -> dict[str, Any]:
        """Load checkpoint from tmp directory."""
        checkpoint_path = self.tmp_dir / f"{name}.json"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def main():
    """Example usage of taxonomy-first pipeline."""
    # Paths (matching two_phase_pipeline)
    base_dir = Path(__file__).parent.parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    probtp_path = output_base / "File #3 - Panorama FMC 2025.json"
    axa_path = output_base / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"
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
        categories_to_process=["hospitalisation", "optique"],  # Test with 2 categories
    )

    # Run pipeline
    results = pipeline.run(
        probtp_level="P4",
        axa_level="Base Obligatoire",
        skip_taxonomy=False,
        skip_extraction=False,
        skip_assembly=False,
        skip_analysis=False,
    )

    print("\n✅ Pipeline complete!")
    print(f"   Output directory: {output_dir}")


if __name__ == "__main__":
    main()
