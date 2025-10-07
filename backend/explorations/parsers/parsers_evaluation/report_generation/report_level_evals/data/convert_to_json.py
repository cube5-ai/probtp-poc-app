"""
Convert ground truth dataset from markdown to JSON format.

This script reads evaluation questions from markdown tables organized by section,
and converts them to structured JSON format for use in report-level evaluations.

Expected sections:
- Facts: Direct factual questions about specific provider coverage
- Inference: Questions requiring logical deduction
- Comparisons: Questions comparing ProBTP vs AXA
"""

import json
import re
import uuid
from pathlib import Path


def parse_markdown_tables(markdown_file: Path) -> list[dict]:
    """
    Parse markdown file with multiple sections containing tables.

    Returns list of question objects with:
    - section: "Facts", "Inference", or "Comparisons"
    - task_type: Type of question
    - scope: Provider and/or level info
    - question: The question text
    - answer: The expected answer
    - id: Unique identifier
    """
    with open(markdown_file, "r", encoding='utf-8') as f:
        content = f.read()

    all_questions = []
    current_section = None

    # Split by ## headers to identify sections
    sections = re.split(r'^##\s+(.+)$', content, flags=re.MULTILINE)

    for i in range(1, len(sections), 2):
        section_name = sections[i].strip()
        section_content = sections[i + 1] if i + 1 < len(sections) else ""

        # Normalize section name
        if "fact" in section_name.lower() and "inference" not in section_name.lower():
            current_section = "Facts"
        elif "inference" in section_name.lower() or "infer" in section_name.lower():
            current_section = "Inference"
        elif "comparison" in section_name.lower():
            current_section = "Comparisons"
        else:
            continue

        # Parse table in this section
        questions = parse_table_by_section(section_content, current_section)
        all_questions.extend(questions)

    return all_questions


def parse_table_by_section(content: str, section: str) -> list[dict]:
    """Parse table based on section type - handles multiline table cells."""
    lines = content.split('\n')

    # Find table start and merge multiline rows
    table_lines = []
    in_table = False
    current_row = ""
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if line.startswith('|'):
            in_table = True

            # A complete row ends with | and has proper structure
            # A continuation line may start with text (not |) or not end with |
            if line.endswith('|'):
                # This line ends with |, likely a complete row
                if current_row:
                    # We were building a row, complete it
                    current_row += " " + line
                    table_lines.append(current_row)
                    current_row = ""
                else:
                    # Start a new row
                    table_lines.append(line)
            else:
                # This line doesn't end with |, it's the start of a multiline cell
                if current_row:
                    # Save previous row first
                    table_lines.append(current_row)
                current_row = line
        elif in_table:
            # Not a table line anymore
            if current_row:
                table_lines.append(current_row)
                current_row = ""
            break

        i += 1

    # Add last row if exists
    if current_row:
        table_lines.append(current_row)

    if len(table_lines) < 3:  # Need at least header, separator, and one data row
        return []

    # Parse header
    header = [cell.strip() for cell in table_lines[0].split('|')[1:-1]]

    # Skip separator line (table_lines[1])
    data_rows = table_lines[2:]

    questions = []

    for row in data_rows:
        cells = [cell.strip() for cell in row.split('|')[1:-1]]

        # Skip completely empty rows
        if not any(cells) or all(not cell for cell in cells):
            continue

        # Parse based on section type
        if section == "Facts":
            question_obj = parse_facts_row(cells, header)
        elif section == "Inference":
            question_obj = parse_inference_row(cells, header)
        elif section == "Comparisons":
            question_obj = parse_comparison_row(cells, header)
        else:
            continue

        if question_obj:
            question_obj["section"] = section
            question_obj["id"] = str(uuid.uuid4())[:8]
            questions.append(question_obj)

    return questions


def parse_facts_row(cells: list[str], header: list[str]) -> dict | None:
    """
    Parse a Facts table row.
    Expected columns: Question Type | Provider | Contract Level | Question | Answer
    """
    if len(cells) < 5:
        return None

    question_type = cells[0].strip()
    provider = cells[1].strip()
    contract_level = cells[2].strip()
    question = cells[3].strip()
    answer = cells[4].strip()

    # Skip empty rows
    if not question or not answer:
        return None

    return {
        "task_type": question_type or "Fact",
        "provider": provider,
        "contract_level": contract_level,
        "scope": f"{provider} {contract_level}".strip(),
        "question": question,
        "answer": answer
    }


def parse_inference_row(cells: list[str], header: list[str]) -> dict | None:
    """
    Parse an Inference table row.
    Expected columns: Question Type | Provider | Contract Level | Question | Answer
    """
    if len(cells) < 5:
        return None

    question_type = cells[0].strip()
    provider = cells[1].strip()
    contract_level = cells[2].strip()
    question = cells[3].strip()
    answer = cells[4].strip()

    # Skip empty rows
    if not question or not answer:
        return None

    return {
        "task_type": question_type or "Inferred Fact",
        "provider": provider,
        "contract_level": contract_level,
        "scope": f"{provider} {contract_level}".strip(),
        "question": question,
        "answer": answer
    }


def parse_comparison_row(cells: list[str], header: list[str]) -> dict | None:
    """
    Parse a Comparisons table row.
    Expected columns: ProBTP Level | AXA Level | Question | Answer
    """
    if len(cells) < 4:
        return None

    probtp_level = cells[0].strip()
    axa_level = cells[1].strip()
    question = cells[2].strip()
    answer = cells[3].strip()

    # Skip rows where both question AND answer are empty
    if not question or not answer:
        return None

    # Handle multiline questions and answers
    question = re.sub(r'\s+', ' ', question).strip()
    answer = re.sub(r'\s+', ' ', answer).strip()

    # Build scope - handle cases where level might be empty
    if probtp_level and axa_level:
        scope = f"ProBTP {probtp_level} vs AXA {axa_level}"
    elif axa_level:
        scope = f"ProBTP vs AXA {axa_level}"
    elif probtp_level:
        scope = f"ProBTP {probtp_level} vs AXA"
    else:
        scope = "ProBTP vs AXA"

    return {
        "task_type": "Comparison",
        "probtp_level": probtp_level or "",
        "axa_level": axa_level or "",
        "scope": scope,
        "question": question,
        "answer": answer
    }


def write_to_json(data: list[dict], json_file: Path) -> None:
    """Write the data to a JSON file."""
    with open(json_file, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_to_jsonl(data: list[dict], jsonl_file: Path) -> None:
    """Write the data to a JSONL file (one JSON object per line)."""
    with open(jsonl_file, "w", encoding='utf-8') as f:
        for obj in data:
            json.dump(obj, f, ensure_ascii=False)
            f.write('\n')


def print_statistics(data: list[dict]) -> None:
    """Print statistics about the parsed data."""
    total = len(data)
    by_section = {}
    by_task_type = {}

    for item in data:
        section = item.get("section", "Unknown")
        task_type = item.get("task_type", "Unknown")

        by_section[section] = by_section.get(section, 0) + 1
        by_task_type[task_type] = by_task_type.get(task_type, 0) + 1

    print(f"\nTotal questions: {total}")
    print(f"\nBy section:")
    for section, count in by_section.items():
        print(f"  {section}: {count}")

    print(f"\nBy task type:")
    for task_type, count in by_task_type.items():
        print(f"  {task_type}: {count}")


if __name__ == "__main__":
    data_dir = Path(__file__).parent
    markdown_file = data_dir / "dataset.md"

    if not markdown_file.exists():
        print(f"Error: {markdown_file} not found")
        print("Please create dataset.md with your evaluation questions")
        exit(1)

    print(f"Processing {markdown_file.name}...")
    data = parse_markdown_tables(markdown_file)

    if not data:
        print("No questions found in the dataset")
        print("Please check the format of your markdown tables")
        exit(1)

    # Write to JSON file
    json_file = data_dir / "dataset.json"
    write_to_json(data, json_file)
    print(f"✓ Written {json_file.name}")

    # Write to JSONL file (one object per line)
    jsonl_file = data_dir / "dataset.jsonl"
    write_to_jsonl(data, jsonl_file)
    print(f"✓ Written {jsonl_file.name}")

    # Print statistics
    print_statistics(data)
