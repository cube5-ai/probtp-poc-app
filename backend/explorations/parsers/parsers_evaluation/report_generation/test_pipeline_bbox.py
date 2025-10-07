"""
Test script to verify bounding box conversion in pipeline.

This loads existing checkpoints and only runs Phase 10 (grounding enrichment)
to test the new absolute coordinate conversion.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from pipelines.taxonomy_first_pipeline import TaxonomyFirstPipeline


async def test_phase_10_only():
    """Test Phase 10 (grounding enrichment) with absolute coordinates."""
    print("\n" + "=" * 80)
    print("Testing Phase 10: Bounding Box Conversion")
    print("=" * 80 + "\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    output_base = base_dir / "output" / "landing_ai_xtd"

    probtp_path = output_base / "File #3 - Panorama FMC 2025.json"
    axa_path = (
        output_base
        / "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.json"
    )
    output_dir = Path(__file__).parent / "output" / "taxonomy_first"

    # Check if documents exist
    if not probtp_path.exists():
        print(f"Error: ProBTP document not found: {probtp_path}")
        return False

    if not axa_path.exists():
        print(f"Error: AXA document not found: {axa_path}")
        return False

    # Create pipeline
    pipeline = TaxonomyFirstPipeline(
        probtp_doc_path=probtp_path,
        axa_doc_path=axa_path,
        output_dir=output_dir,
        model_name="gemini-2.5-flash",
        categories_to_process=["Soins Courants"],  # Just one category for testing
    )

    # Run pipeline (skip everything except Phase 10)
    try:
        results = await pipeline.run(
            probtp_levels=["S4", "P5"],
            axa_levels=["Base obligatoire"],
            skip_taxonomy=True,
            skip_extraction=True,
            skip_assembly=True,
            skip_analysis=True,
            skip_summary=True,
            skip_recommendation=True,
            skip_grounding=False,  # Run grounding with new conversion
        )

        # Check results
        json_output_path = results.get("json_output_path")
        if not json_output_path or not Path(json_output_path).exists():
            print("✗ JSON output not found")
            return False

        print(f"\n✓ Pipeline completed successfully")
        print(f"  Output: {json_output_path}")

        # Verify bounding box format
        with open(json_output_path, "r") as f:
            data = json.load(f)

        # Find first bounding box
        for analysis in data.get("analyses", []):
            for row in analysis.get("annotated_table", {}).get("rows", []):
                for cell in row.get("cells", []):
                    bboxes = cell.get("bounding_boxes", [])
                    if bboxes:
                        bbox = bboxes[0]
                        print(f"\n✓ Found bounding box:")
                        print(f"  file_id: {bbox['file_id']}")
                        print(f"  page: {bbox['page']}")

                        bbox_data = bbox['bounding_box']
                        print(f"  bounding_box format: {list(bbox_data.keys())}")

                        # Check if it has absolute coordinates
                        if 'x1' in bbox_data and 'y1' in bbox_data and 'width' in bbox_data:
                            print(f"\n✓ Absolute coordinates detected!")
                            print(f"    x1: {bbox_data['x1']:.2f}")
                            print(f"    y1: {bbox_data['y1']:.2f}")
                            print(f"    x2: {bbox_data['x2']:.2f}")
                            print(f"    y2: {bbox_data['y2']:.2f}")
                            print(f"    width: {bbox_data['width']:.2f}")
                            print(f"    height: {bbox_data['height']:.2f}")
                            return True
                        else:
                            print(f"\n✗ Still using relative coordinates")
                            print(f"    {bbox_data}")
                            return False

        print("\n✗ No bounding boxes found")
        return False

    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_phase_10_only())
    print("\n" + "=" * 80)
    if result:
        print("✓ Test PASSED: Bounding boxes converted to absolute coordinates")
    else:
        print("✗ Test FAILED")
    print("=" * 80)
    sys.exit(0 if result else 1)
