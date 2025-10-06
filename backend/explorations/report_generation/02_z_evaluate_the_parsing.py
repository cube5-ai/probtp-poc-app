"""
Parsing evaluation script for report generation exploration
- Analyze the results from Mistral OCR parsing
- Generate quality reports and metrics
- Compare parsing performance across files

This script evaluates the parsing results stored by 02_read_and_parse_file.py

Original evaluation ideas:
- Using a list of questions on the raw and parsed documents identify the errors in the document generation
- Ask LLMs to check the consistency of the blocks (like unfinished sentences)
- Ask LLMs to check the self containance of the block, i.e. does the block content reference something outside of the block, like footnotes, ...?
- Leverage Langfuse for logging
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.file import File
from app.models.project import Project

# Initialize services
settings = get_settings()


def get_test_project_id() -> Optional[str]:
    """Get the test project ID created by setup script"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == "Report Generation Test").first()
        if not project:
            print("❌ Test project not found. Please run 00_config_and_setup.py first.")
            return None
        return str(project.id)
    finally:
        db.close()


def get_parsed_files(project_id: str) -> List[File]:
    """Get all files that have been parsed"""
    db = SessionLocal()
    try:
        files = db.query(File).filter(
            File.project_id == project_id,
            File.status == 'ready'
        ).all()

        # Filter files that have parsing metadata
        parsed_files = []
        for file in files:
            if (hasattr(file, 'metadata') and file.metadata and
                'parsing' in file.metadata):
                parsed_files.append(file)

        print(f"Found {len(parsed_files)} parsed files:")
        for file in parsed_files:
            parsing_metadata = file.metadata['parsing']
            print(f"  - {file.original_name}")
            print(f"    Parsed at: {parsing_metadata.get('parsed_at', 'N/A')}")
            print(f"    Status: {parsing_metadata.get('parsing_status', 'N/A')}")
            print(f"    Blocks: {parsing_metadata.get('content_blocks_count', 0)}")

        return parsed_files
    finally:
        db.close()


def analyze_parsing_quality(file_record: File) -> Dict[str, Any]:
    """Analyze the parsing quality for a single file"""
    parsing_metadata = file_record.metadata['parsing']

    analysis = {
        "file_name": file_record.original_name,
        "file_size": file_record.file_size,
        "parsing_status": parsing_metadata.get('parsing_status', 'unknown'),
        "duration_seconds": parsing_metadata.get('duration_seconds', 0),
        "content_blocks_count": parsing_metadata.get('content_blocks_count', 0),
        "sample_blocks": parsing_metadata.get('content_blocks', []),
    }

    # Calculate processing speed metrics
    if analysis['duration_seconds'] > 0:
        analysis['bytes_per_second'] = file_record.file_size / analysis['duration_seconds']
        analysis['blocks_per_second'] = analysis['content_blocks_count'] / analysis['duration_seconds']
    else:
        analysis['bytes_per_second'] = 0
        analysis['blocks_per_second'] = 0

    # Analyze sample blocks if available
    sample_blocks = analysis['sample_blocks']
    if sample_blocks:
        # Block type distribution
        block_types = Counter(block.get('block_type', 'unknown') for block in sample_blocks)
        analysis['block_types'] = dict(block_types)

        # Content analysis
        total_content_chars = sum(len(block.get('content', '')) for block in sample_blocks)
        analysis['sample_content_chars'] = total_content_chars

        # Confidence analysis
        confidence_scores = [block.get('confidence_score') for block in sample_blocks
                           if block.get('confidence_score') is not None]
        if confidence_scores:
            analysis['avg_confidence'] = sum(confidence_scores) / len(confidence_scores)
            analysis['min_confidence'] = min(confidence_scores)
            analysis['max_confidence'] = max(confidence_scores)
            analysis['high_confidence_ratio'] = sum(1 for score in confidence_scores if score > 0.9) / len(confidence_scores)
        else:
            analysis['avg_confidence'] = 0
            analysis['min_confidence'] = 0
            analysis['max_confidence'] = 0
            analysis['high_confidence_ratio'] = 0

        # Page analysis
        pages = set(block.get('page_number') for block in sample_blocks
                   if block.get('page_number') is not None)
        analysis['pages_in_sample'] = len(pages)

    else:
        analysis['block_types'] = {}
        analysis['sample_content_chars'] = 0
        analysis['avg_confidence'] = 0
        analysis['min_confidence'] = 0
        analysis['max_confidence'] = 0
        analysis['high_confidence_ratio'] = 0
        analysis['pages_in_sample'] = 0

    return analysis


def generate_quality_report(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate an overall quality report from individual file analyses"""
    if not analyses:
        return {"error": "No parsed files to analyze"}

    successful_parses = [a for a in analyses if a['parsing_status'] == 'completed']

    report = {
        "summary": {
            "total_files": len(analyses),
            "successful_parses": len(successful_parses),
            "success_rate": len(successful_parses) / len(analyses) if analyses else 0,
            "total_file_size": sum(a['file_size'] for a in analyses),
            "total_processing_time": sum(a['duration_seconds'] for a in analyses),
            "total_content_blocks": sum(a['content_blocks_count'] for a in analyses)
        },
        "performance_metrics": {},
        "quality_metrics": {},
        "file_details": analyses
    }

    if successful_parses:
        # Performance metrics
        durations = [a['duration_seconds'] for a in successful_parses if a['duration_seconds'] > 0]
        if durations:
            report["performance_metrics"] = {
                "avg_processing_time": sum(durations) / len(durations),
                "min_processing_time": min(durations),
                "max_processing_time": max(durations),
                "avg_bytes_per_second": sum(a['bytes_per_second'] for a in successful_parses if a['bytes_per_second'] > 0) / len(successful_parses),
                "avg_blocks_per_second": sum(a['blocks_per_second'] for a in successful_parses if a['blocks_per_second'] > 0) / len(successful_parses)
            }

        # Quality metrics
        all_confidences = [a['avg_confidence'] for a in successful_parses if a['avg_confidence'] > 0]
        if all_confidences:
            report["quality_metrics"] = {
                "avg_confidence_score": sum(all_confidences) / len(all_confidences),
                "min_avg_confidence": min(all_confidences),
                "max_avg_confidence": max(all_confidences),
                "files_with_high_confidence": sum(1 for a in successful_parses if a['high_confidence_ratio'] > 0.8),
                "high_confidence_file_ratio": sum(1 for a in successful_parses if a['high_confidence_ratio'] > 0.8) / len(successful_parses)
            }

        # Block type analysis across all files
        all_block_types = Counter()
        for analysis in successful_parses:
            for block_type, count in analysis['block_types'].items():
                all_block_types[block_type] += count

        report["block_type_distribution"] = dict(all_block_types)

    return report


def print_detailed_report(report: Dict[str, Any]):
    """Print a detailed analysis report"""
    print(f"{'='*80}")
    print("📊 MISTRAL OCR PARSING QUALITY REPORT")
    print(f"{'='*80}")
    print(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # Summary
    summary = report["summary"]
    print("📈 SUMMARY")
    print("-" * 40)
    print(f"Total files analyzed: {summary['total_files']}")
    print(f"Successful parses: {summary['successful_parses']}")
    print(f"Success rate: {summary['success_rate']:.1%}")
    print(f"Total file size processed: {summary['total_file_size']:,} bytes ({summary['total_file_size']/1024/1024:.1f} MB)")
    print(f"Total processing time: {summary['total_processing_time']:.1f} seconds")
    print(f"Total content blocks extracted: {summary['total_content_blocks']:,}")
    print()

    # Performance metrics
    if "performance_metrics" in report and report["performance_metrics"]:
        perf = report["performance_metrics"]
        print("⚡ PERFORMANCE METRICS")
        print("-" * 40)
        print(f"Average processing time: {perf['avg_processing_time']:.2f} seconds")
        print(f"Processing time range: {perf['min_processing_time']:.2f} - {perf['max_processing_time']:.2f} seconds")
        print(f"Average throughput: {perf['avg_bytes_per_second']:,.0f} bytes/sec ({perf['avg_bytes_per_second']/1024:.0f} KB/sec)")
        print(f"Average block extraction rate: {perf['avg_blocks_per_second']:.1f} blocks/sec")
        print()

    # Quality metrics
    if "quality_metrics" in report and report["quality_metrics"]:
        quality = report["quality_metrics"]
        print("🎯 QUALITY METRICS")
        print("-" * 40)
        print(f"Average confidence score: {quality['avg_confidence_score']:.3f}")
        print(f"Confidence range: {quality['min_avg_confidence']:.3f} - {quality['max_avg_confidence']:.3f}")
        print(f"Files with high confidence (>80%): {quality['files_with_high_confidence']}/{summary['successful_parses']} ({quality['high_confidence_file_ratio']:.1%})")
        print()

    # Block type distribution
    if "block_type_distribution" in report and report["block_type_distribution"]:
        print("📝 CONTENT BLOCK TYPES")
        print("-" * 40)
        block_types = report["block_type_distribution"]
        total_blocks = sum(block_types.values())
        for block_type, count in sorted(block_types.items(), key=lambda x: x[1], reverse=True):
            percentage = count / total_blocks * 100 if total_blocks > 0 else 0
            print(f"{block_type:15}: {count:6,} blocks ({percentage:5.1f}%)")
        print()

    # Individual file details
    print("📄 INDIVIDUAL FILE RESULTS")
    print("-" * 40)
    for analysis in report["file_details"]:
        status_icon = "✅" if analysis["parsing_status"] == "completed" else "❌"
        print(f"{status_icon} {analysis['file_name']}")

        if analysis["parsing_status"] == "completed":
            print(f"     Size: {analysis['file_size']:,} bytes, Duration: {analysis['duration_seconds']:.2f}s")
            print(f"     Blocks: {analysis['content_blocks_count']:,}, Avg confidence: {analysis['avg_confidence']:.3f}")
            print(f"     Throughput: {analysis['bytes_per_second']:,.0f} bytes/sec")

            if analysis['block_types']:
                types_str = ', '.join(f"{k}:{v}" for k, v in analysis['block_types'].items())
                print(f"     Block types: {types_str}")
        else:
            print(f"     Status: {analysis['parsing_status']}")
        print()

    print("💡 RECOMMENDATIONS")
    print("-" * 40)

    # Performance recommendations
    if report["summary"]["success_rate"] < 1.0:
        failed_count = report["summary"]["total_files"] - report["summary"]["successful_parses"]
        print(f"• {failed_count} file(s) failed to parse - check file formats and sizes")

    if "quality_metrics" in report and report["quality_metrics"]:
        avg_confidence = report["quality_metrics"]["avg_confidence_score"]
        if avg_confidence < 0.8:
            print(f"• Average confidence score is {avg_confidence:.3f} - consider image quality improvements")
        elif avg_confidence > 0.95:
            print(f"• Excellent confidence score ({avg_confidence:.3f}) - parsing quality is very high")

    if "performance_metrics" in report and report["performance_metrics"]:
        avg_time = report["performance_metrics"]["avg_processing_time"]
        if avg_time > 30:
            print(f"• Processing time averaging {avg_time:.1f}s - consider optimizing for production")
        elif avg_time < 5:
            print(f"• Fast processing ({avg_time:.1f}s average) - good performance for production")

    print()


def export_report_to_json(report: Dict[str, Any], output_path: Optional[str] = None):
    """Export the report to a JSON file"""
    if not output_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"parsing_quality_report_{timestamp}.json"

    try:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"📄 Report exported to: {output_path}")
    except Exception as e:
        print(f"❌ Failed to export report: {e}")


def analyze_content_samples(analyses: List[Dict[str, Any]]):
    """Analyze and display content samples from parsing"""
    print(f"{'='*80}")
    print("📖 CONTENT SAMPLES")
    print(f"{'='*80}")

    for analysis in analyses:
        if analysis["parsing_status"] != "completed" or not analysis["sample_blocks"]:
            continue

        print(f"\n📄 {analysis['file_name']}")
        print("-" * 60)

        sample_blocks = analysis["sample_blocks"][:5]  # Show first 5 blocks

        for i, block in enumerate(sample_blocks, 1):
            block_type = block.get('block_type', 'unknown')
            page_num = block.get('page_number', 'N/A')
            confidence = block.get('confidence_score', 0)
            content = block.get('content', '')[:100]  # First 100 chars

            print(f"  Block {i} [{block_type}] (Page {page_num}, Confidence: {confidence:.3f})")
            print(f"    Content: {content}...")

            if block.get('bounding_box'):
                bbox = block['bounding_box']
                print(f"    Position: ({bbox['x']:.3f}, {bbox['y']:.3f}) Size: {bbox['width']:.3f}×{bbox['height']:.3f}")
            print()


def main():
    """Main evaluation function"""
    print("=== Mistral OCR Parsing Evaluation ===")
    print("Analyzing results from the parsing service")
    print()

    # Get test project
    project_id = get_test_project_id()
    if not project_id:
        return

    print(f"Using test project: {project_id}")

    # Get parsed files
    parsed_files = get_parsed_files(project_id)

    if not parsed_files:
        print("❌ No parsed files found")
        print("Please run 02_read_and_parse_file.py first to parse some files")
        return

    print(f"\n🔍 Analyzing {len(parsed_files)} parsed files...")
    print()

    # Analyze each file
    analyses = []
    for file_record in parsed_files:
        try:
            analysis = analyze_parsing_quality(file_record)
            analyses.append(analysis)
        except Exception as e:
            print(f"❌ Failed to analyze {file_record.original_name}: {e}")

    if not analyses:
        print("❌ No files could be analyzed")
        return

    # Generate quality report
    report = generate_quality_report(analyses)

    # Print detailed report
    print_detailed_report(report)

    # Show content samples
    analyze_content_samples(analyses)

    # Export report
    export_report_to_json(report)

    print("✅ Evaluation complete!")
    print("\nNext steps:")
    print("1. Review quality metrics to assess parsing accuracy")
    print("2. Check content samples for proper text extraction")
    print("3. Use parsing results for report generation in subsequent scripts")


if __name__ == "__main__":
    main()