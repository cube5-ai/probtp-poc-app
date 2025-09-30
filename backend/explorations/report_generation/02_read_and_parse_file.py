"""
File parsing script for report generation exploration
- Read files from cloud storage using the storage service
- Parse files with Mistral OCR service via the parsing service
- Store the resulting content blocks in the database

This script leverages the new parsing service abstraction layer to:
1. Validate files before parsing
2. Use Mistral OCR for document processing
3. Store structured content blocks for report generation
"""
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import ParsingLogger
from app.models.file import File
from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest
from app.models.project import Project
from app.services.content_block_service import ContentBlockService
from app.services.parsing.service import ParsingService
from app.services.parsing.validation import FileValidationService
from app.services.storage_service import StorageService

# Initialize services
settings = get_settings()
validation_service = FileValidationService()
storage_service = StorageService()

settings = get_settings().get_parsing_service_configs()


# Configure Mistral OCR for exploration
mistral_config = settings["mistral_ocr"]


# Initialize parsing service with Mistral OCR only
parsing_service = ParsingService({"mistral_ocr": mistral_config})


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


def get_ready_files(project_id: str) -> List[File]:
    """Get all files that are ready for parsing"""
    db = SessionLocal()
    try:
        files = db.query(File).filter(
            File.project_id == project_id,
            File.status == 'ready'
        ).all()

        print(f"Found {len(files)} ready files for parsing:")
        for file in files:
            print(f"  - {file.original_name} (ID: {str(file.id)[:8]}...)")
            print(f"    Size: {file.file_size} bytes")
            print(f"    Storage: {file.storage_path}")

        return files
    finally:
        db.close()


async def validate_file_for_parsing(file_record: File) -> Dict[str, Any]:
    """Validate a file before parsing with Mistral OCR"""
    print(f"\n📋 Validating {file_record.original_name} for Mistral OCR...")

    try:
        # Create parsing request for validation
        parsing_request = ParsingRequest(
            file_path=f"gs://{file_record.storage_path}",
            service_name="mistral_ocr",
            timeout_seconds=60,
            options={}
        )

        # Validate using the parsing service
        validation_result = await parsing_service.validate_file(parsing_request)

        print(f"  File format: {validation_result['format']}")
        print(f"  File size: {validation_result['file_size']} bytes")
        print(f"  Estimated pages: {validation_result['estimated_pages']}")
        print(f"  Valid for parsing: {validation_result['valid']}")

        if validation_result['errors']:
            print("  Validation errors:")
            for error in validation_result['errors']:
                print(f"    - {error}")

        return validation_result

    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return {
            "valid": False,
            "errors": [f"Validation exception: {str(e)}"],
            "file_size": file_record.file_size,
            "format": "unknown",
            "estimated_pages": 1
        }


async def parse_file_with_mistral(file_record: File) -> Optional[Dict[str, Any]]:
    """Parse a file using Mistral OCR service"""
    print(f"\n🔍 Parsing {file_record.original_name} with Mistral OCR...")

    start_time = time.time()
    correlation_id = f"parse_{str(file_record.id)[:8]}"

    try:
        # Generate a signed URL for the file
        print(f"  Generating signed URL for {file_record.storage_path}...")
        signed_url = storage_service.generate_download_url(
            file_record.storage_path,
            expiration_minutes=15  # 15 minutes should be enough for parsing
        )
        print(f"  ✅ Generated signed URL (expires in 15 minutes)")

        # Log parsing initiation
        ParsingLogger.log_parsing_initiated(
            file_path=signed_url,
            service_name="mistral_ocr",
            correlation_id=correlation_id,
            file_size=file_record.file_size,
            timeout_seconds=60
        )

        # Create parsing request with signed URL
        parsing_request = ParsingRequest(
            file_path=signed_url,
            service_name="mistral_ocr",
            timeout_seconds=60,
            options={
                "correlation_id": correlation_id,
                "file_id": file_record.id,
                "include_image_base64": True
            }
        )

        # Parse the document
        parsed_document = await parsing_service.parse_document(parsing_request)

        duration = time.time() - start_time

        print(f"  ✅ Parsing completed in {duration:.2f}s")
        print(f"  Status: {parsed_document.status}")
        print(f"  Document ID: {parsed_document.document_id}")
        print(f"  Content blocks: {len(parsed_document.content_blocks)}")

        if parsed_document.status == "completed":
            # Log successful parsing
            ParsingLogger.log_parsing_completed(
                file_path=f"gs://{file_record.storage_path}",
                service_name="mistral_ocr",
                correlation_id=correlation_id,
                duration_seconds=duration,
                status=parsed_document.status,
                blocks_count=len(parsed_document.content_blocks)
            )

            # Log performance metrics
            ParsingLogger.log_performance_metrics(
                service_name="mistral_ocr",
                file_size=file_record.file_size,
                page_count=len(set(block.page_number for block in parsed_document.content_blocks)),
                duration_seconds=duration,
                status=parsed_document.status,
                correlation_id=correlation_id
            )

            return {
                "parsed_document": parsed_document,
                "correlation_id": correlation_id,
                "duration_seconds": duration
            }
        else:
            # Log parsing failure
            error_msg = parsed_document.error_message or "Unknown parsing error"
            ParsingLogger.log_parsing_failed(
                file_path=f"gs://{file_record.storage_path}",
                service_name="mistral_ocr",
                correlation_id=correlation_id,
                error=error_msg,
                duration_seconds=duration
            )

            print(f"  ❌ Parsing failed: {error_msg}")
            return None

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)

        # Log parsing exception
        ParsingLogger.log_parsing_failed(
            file_path=f"gs://{file_record.storage_path}",
            service_name="mistral_ocr",
            correlation_id=correlation_id,
            error=error_msg,
            error_type=type(e).__name__,
            duration_seconds=duration
        )

        print(f"  ❌ Parsing exception: {error_msg}")
        return None


def analyze_content_blocks(parsed_result: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the parsed content blocks for insights"""
    parsed_document = parsed_result["parsed_document"]
    content_blocks = parsed_document.content_blocks

    print(f"\n📊 Analyzing {len(content_blocks)} content blocks...")

    # Analyze block types
    block_types = {}
    total_characters = 0
    pages_with_content = set()
    high_confidence_blocks = 0

    for block in content_blocks:
        # Count block types
        block_type = block.block_type
        block_types[block_type] = block_types.get(block_type, 0) + 1

        # Count characters
        total_characters += len(block.content or "")

        # Track pages
        if block.page_number:
            pages_with_content.add(block.page_number)

        # Count high confidence blocks
        if block.confidence_score and block.confidence_score > 0.9:
            high_confidence_blocks += 1

    analysis = {
        "total_blocks": len(content_blocks),
        "block_types": block_types,
        "total_characters": total_characters,
        "pages_processed": len(pages_with_content),
        "high_confidence_blocks": high_confidence_blocks,
        "confidence_rate": high_confidence_blocks / len(content_blocks) if content_blocks else 0
    }

    print(f"  Total blocks: {analysis['total_blocks']}")
    print(f"  Block types: {dict(sorted(analysis['block_types'].items()))}")
    print(f"  Total characters: {analysis['total_characters']:,}")
    print(f"  Pages processed: {analysis['pages_processed']}")
    print(f"  High confidence blocks: {analysis['high_confidence_blocks']} ({analysis['confidence_rate']:.1%})")

    return analysis


def store_content_blocks_in_database(file_record: File, parsed_result: Dict[str, Any]) -> bool:
    """Store parsed content blocks in database using proper ContentBlockDB table"""
    print(f"\n💾 Storing content blocks in database...")

    try:
        db = SessionLocal()
        parsed_document = parsed_result["parsed_document"]

        # Delete existing content blocks for this file (in case of reprocessing)
        ContentBlockService.delete_content_blocks_for_file(db, file_record.id)

        # Save new content blocks using the service
        saved_blocks = ContentBlockService.save_parsed_document_blocks(
            db=db,
            file_id=file_record.id,
            parsed_document=parsed_document
        )

        print(f"  ✅ Stored {len(saved_blocks)} content blocks in database")
        print(f"  📊 Block types: {', '.join(set(block.block_type for block in saved_blocks))}")

        # Count blocks by type
        type_counts = {}
        for block in saved_blocks:
            type_counts[block.block_type] = type_counts.get(block.block_type, 0) + 1

        for block_type, count in type_counts.items():
            print(f"    - {block_type}: {count}")

        return True

    except Exception as e:
        print(f"  ❌ Database storage failed: {e}")
        return False
    finally:
        db.close()


async def process_single_file(file_record: File) -> Dict[str, Any]:
    """Process a single file through the complete parsing pipeline"""
    print(f"\n{'='*60}")
    print(f"📄 Processing: {file_record.original_name}")
    print(f"   File ID: {file_record.id}")
    print(f"   Size: {file_record.file_size:,} bytes")
    print(f"   Storage: gs://{file_record.storage_path}")
    print(f"{'='*60}")

    results = {
        "file_id": file_record.id,
        "file_name": file_record.original_name,
        "validation_passed": False,
        "parsing_succeeded": False,
        "storage_succeeded": False,
        "error": None
    }

    try:
        # Step 1: Validate file
        validation_result = await validate_file_for_parsing(file_record)
        results["validation_result"] = validation_result
        results["validation_passed"] = validation_result["valid"]

        if not validation_result["valid"]:
            results["error"] = f"Validation failed: {'; '.join(validation_result['errors'])}"
            return results

        # Step 2: Parse file
        parsed_result = await parse_file_with_mistral(file_record)
        results["parsing_succeeded"] = parsed_result is not None

        if not parsed_result:
            results["error"] = "Parsing failed"
            return results

        # Step 3: Analyze content
        analysis = analyze_content_blocks(parsed_result)
        results["content_analysis"] = analysis

        # Step 4: Store results
        storage_success = store_content_blocks_in_database(file_record, parsed_result)
        results["storage_succeeded"] = storage_success

        if not storage_success:
            results["error"] = "Database storage failed"

        return results

    except Exception as e:
        results["error"] = f"Processing exception: {str(e)}"
        print(f"❌ Processing failed: {e}")
        return results


async def main():
    """Main processing function"""
    print("=== Document Parsing with Mistral OCR ===")
    print("Leveraging the new parsing service abstraction layer")
    print()

    # Get test project
    project_id = get_test_project_id()
    if not project_id:
        return

    print(f"Using test project: {project_id}")

    # Check parsing service health
    try:
        health_status = await parsing_service.check_service_health("mistral_ocr")
        print(f"Mistral OCR service status: {health_status['status']}")
        ParsingLogger.log_service_health_checked(
            service_name="mistral_ocr",
            status=health_status['status'],
            response_time_ms=health_status.get('response_time', 0)
        )
    except Exception as e:
        print(f"⚠️  Could not check service health: {e}")

    # Get files ready for parsing
    ready_files = get_ready_files(project_id)

    if not ready_files:
        print("❌ No files ready for parsing found")
        print("Please run 01_upload_files.py first to upload some test files")
        return

    # Process each file
    processing_results = []
    successful_parses = 0

    for file_record in ready_files:
        result = await process_single_file(file_record)
        processing_results.append(result)

        if result["parsing_succeeded"] and result["storage_succeeded"]:
            successful_parses += 1

    # Summary report
    print(f"\n{'='*60}")
    print("📈 PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f"Total files processed: {len(ready_files)}")
    print(f"Successfully parsed: {successful_parses}")
    print(f"Success rate: {successful_parses/len(ready_files):.1%}")
    print()

    # Detailed results
    for result in processing_results:
        status = "✅ SUCCESS" if (result["parsing_succeeded"] and result["storage_succeeded"]) else "❌ FAILED"
        print(f"{status} - {result['file_name']}")

        if result["error"]:
            print(f"         Error: {result['error']}")
        elif "content_analysis" in result:
            analysis = result["content_analysis"]
            print(f"         Blocks: {analysis['total_blocks']}, Characters: {analysis['total_characters']:,}")
            print(f"         Pages: {analysis['pages_processed']}, Confidence: {analysis['confidence_rate']:.1%}")
        print()

    if successful_parses > 0:
        print("Next steps:")
        print("1. Check the database for stored content blocks")
        print("2. Run subsequent report generation scripts")
        print("3. Analyze parsing quality and performance metrics")
    else:
        print("⚠️  No files were successfully parsed. Check:")
        print("1. File formats are supported (.pdf, .png, .jpg, .jpeg)")
        print("2. Files are not corrupted or too large")
        print("3. Mistral OCR service configuration is correct")


if __name__ == "__main__":
    asyncio.run(main())