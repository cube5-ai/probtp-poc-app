#!/usr/bin/env python3
"""
Temporary script to compare schemas between two JSON comparison reports.
For arrays, extracts the schema of the most complete element.
"""

import json
from typing import Any, Dict, Set, List
from pathlib import Path


def get_most_complete_element(arr: List[Any]) -> Any:
    """Get the element with the most fields from an array."""
    if not arr:
        return None

    if not isinstance(arr[0], dict):
        return arr[0]

    # Find the dict with the most keys
    return max(arr, key=lambda x: len(x) if isinstance(x, dict) else 0)


def extract_schema(obj: Any, path: str = "") -> Dict[str, str]:
    """
    Recursively extract schema from an object.
    Returns a dict mapping paths to types.
    """
    schema = {}

    if obj is None:
        schema[path] = "null"
    elif isinstance(obj, bool):
        schema[path] = "boolean"
    elif isinstance(obj, int):
        schema[path] = "integer"
    elif isinstance(obj, float):
        schema[path] = "number"
    elif isinstance(obj, str):
        schema[path] = "string"
    elif isinstance(obj, list):
        schema[path] = "array"
        if obj:
            # Get schema of the most complete element
            most_complete = get_most_complete_element(obj)
            element_path = f"{path}[*]"
            schema.update(extract_schema(most_complete, element_path))
    elif isinstance(obj, dict):
        schema[path] = "object"
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            schema.update(extract_schema(value, new_path))
    else:
        schema[path] = str(type(obj).__name__)

    return schema


def compare_schemas(schema1: Dict[str, str], schema2: Dict[str, str], name1: str, name2: str, base_dir: Path) -> None:
    """Compare two schemas and print differences."""
    keys1 = set(schema1.keys())
    keys2 = set(schema2.keys())

    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    common = keys1 & keys2

    # Check for type differences in common keys
    type_differences = {}
    for key in common:
        if schema1[key] != schema2[key]:
            type_differences[key] = (schema1[key], schema2[key])

    # Print results
    print(f"\n{'='*80}")
    print(f"SCHEMA COMPARISON")
    print(f"{'='*80}\n")

    print(f"Document 1: {name1}")
    print(f"Document 2: {name2}\n")

    print(f"Total fields in {name1}: {len(keys1)}")
    print(f"Total fields in {name2}: {len(keys2)}")
    print(f"Common fields: {len(common)}\n")

    if only_in_1:
        print(f"\n{'='*80}")
        print(f"FIELDS ONLY IN {name1} ({len(only_in_1)} fields)")
        print(f"{'='*80}\n")
        # Just show first 10
        for key in sorted(list(only_in_1)[:10]):
            print(f"  {key}")
            print(f"    Type: {schema1[key]}")
        if len(only_in_1) > 10:
            print(f"\n  ... and {len(only_in_1) - 10} more fields")

    if only_in_2:
        print(f"\n{'='*80}")
        print(f"FIELDS ONLY IN {name2} ({len(only_in_2)} fields)")
        print(f"{'='*80}\n")
        for key in sorted(only_in_2):
            print(f"  {key}")
            print(f"    Type: {schema2[key]}")

        # Write these to a separate file for easier inspection
        output_file = base_dir / "output" / "fields_only_in_two_phase.txt"
        with open(output_file, 'w') as f:
            f.write(f"FIELDS ONLY IN {name2} ({len(only_in_2)} fields)\n")
            f.write("="*80 + "\n\n")
            for key in sorted(only_in_2):
                f.write(f"{key}\n")
                f.write(f"  Type: {schema2[key]}\n\n")
        print(f"\n✓ Saved detailed list to: {output_file}")

    if type_differences:
        print(f"\n{'='*80}")
        print(f"TYPE DIFFERENCES IN COMMON FIELDS ({len(type_differences)} fields)")
        print(f"{'='*80}\n")
        for key in sorted(type_differences.keys()):
            type1, type2 = type_differences[key]
            print(f"  {key}")
            print(f"    {name1}: {type1}")
            print(f"    {name2}: {type2}")

    if not only_in_1 and not only_in_2 and not type_differences:
        print("\n✅ SCHEMAS ARE IDENTICAL!\n")


def main():
    # File paths
    base_dir = Path(__file__).parent
    file1 = base_dir / "output" / "taxonomy_first" / "comparison_report_ProBTP_S4_P5_vs_AXA_Base_obligatoire.json"
    file2 = base_dir / "output" / "comparison_report_ProBTP_S2_P4_vs_AXA_Base_Obligatoire_10_05_00_47 (1).json"

    # Read files
    print("\nReading files...")
    with open(file1, 'r', encoding='utf-8') as f:
        data1 = json.load(f)
    print(f"✓ Loaded: {file1.name}")

    with open(file2, 'r', encoding='utf-8') as f:
        data2 = json.load(f)
    print(f"✓ Loaded: {file2.name}")

    # Extract schemas
    print("\nExtracting schemas...")
    schema1 = extract_schema(data1)
    schema2 = extract_schema(data2)
    print(f"✓ Extracted schema from {file1.name}")
    print(f"✓ Extracted schema from {file2.name}")

    # Compare
    compare_schemas(
        schema1,
        schema2,
        "taxonomy_first (S4_P5)",
        "two_phase (S2_P4)",
        base_dir
    )

    # Save schemas to files for inspection
    output_dir = base_dir / "output"
    schema1_path = output_dir / "schema_taxonomy_first.json"
    schema2_path = output_dir / "schema_two_phase.json"

    with open(schema1_path, 'w', encoding='utf-8') as f:
        json.dump(schema1, f, indent=2, ensure_ascii=False)

    with open(schema2_path, 'w', encoding='utf-8') as f:
        json.dump(schema2, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved schema to: {schema1_path}")
    print(f"✓ Saved schema to: {schema2_path}\n")


if __name__ == "__main__":
    main()
