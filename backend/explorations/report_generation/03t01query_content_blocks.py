"""
Query and analyze stored content blocks from the database
"""
import os
import sys
from typing import Any, Dict, List

from sqlalchemy import func

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.content_block_db import ContentBlockDB
from app.models.file import File
from app.models.project import Project
from app.services.content_block_service import ContentBlockService


def get_test_project_files():
    """Get files from the test project"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == "Report Generation Test").first()
        if not project:
            print("❌ Test project not found")
            return []

        files = db.query(File).filter(
            File.project_id == project.id,
            File.status == 'ready'
        ).all()

        print(f"Found {len(files)} files in project '{project.name}'")
        return files

    finally:
        db.close()


def analyze_content_blocks(file_record: File):
    """Analyze content blocks for a file"""
    print(f"\n📊 Analyzing content blocks for: {file_record.original_name}")
    print(f"File ID: {file_record.id}")

    db = SessionLocal()
    try:
        # Get all content blocks for this file
        all_blocks = ContentBlockService.get_content_blocks_for_file(db, file_record.id)

        if not all_blocks:
            print("  ❌ No content blocks found")
            return

        print(f"  📋 Total content blocks: {len(all_blocks)}")

        # Analyze by type
        type_counts: dict[str, int] = {}
        for block in all_blocks:
            type_counts[block.block_type] = type_counts.get(block.block_type, 0) + 1

        print("  📈 Block types:")
        for block_type, count in sorted(type_counts.items()):
            print(f"    - {block_type}: {count}")

        # Analyze by page
        page_counts: dict[int, int] = {}
        for block in all_blocks:
            page = block.page_number or 0
            page_counts[page] = page_counts.get(page, 0) + 1

        print("  📄 Blocks per page:")
        for page, count in sorted(page_counts.items()):
            print(f"    - Page {page}: {count} blocks")

        # Show first few blocks to verify structure
        print("  📝 First 3 content blocks:")
        for i, block in enumerate(all_blocks[:3]):
            content_preview = block.content[:100] + "..." if len(block.content) > 100 else block.content
            print(f"    {i+1}. [{block.block_type}] P{block.page_number} #{block.position}: {content_preview}")

        # Show images separately
        image_blocks = ContentBlockService.get_blocks_by_type(db, file_record.id, "image")
        if image_blocks:
            print(f"  🖼️  Found {len(image_blocks)} images:")
            for img in image_blocks:
                has_base64 = img.metadata and img.metadata.get("has_base64", False)
                coords = img.metadata.get("coordinates", {}) if img.metadata else {}
                print(f"    - {img.content} (Page {img.page_number}, Position {img.position})")
                print(f"      Base64 data: {'Yes' if has_base64 else 'No'}")
                if coords:
                    print(f"      Coordinates: ({coords.get('top_left_x', 0)}, {coords.get('top_left_y', 0)}) to ({coords.get('bottom_right_x', 0)}, {coords.get('bottom_right_y', 0)})")

    finally:
        db.close()


def print_specific_block():
    """Print the content of a specific block ID"""
    print("\n🔍 Looking for block ID: mistral_41227e2d_p1_b2")

    db = SessionLocal()
    try:
        # Query for the specific block
        block = db.query(ContentBlockDB).filter(
            ContentBlockDB.block_id == "mistral_41227e2d_p1_b2"
        ).first()

        if block:
            print(f"✅ Found block!")
            print(f"   Block ID: {block.block_id}")
            print(f"   Block Type: {block.block_type}")
            print(f"   Page: {block.page_number}")
            print(f"   Position: {block.position}")
            print(f"   Parsing Service: {block.parsing_service}")
            print(f"   Document ID: {block.document_id}")
            print(f"   Content Length: {len(block.content)} characters")
            print("\n📄 Content:")
            print("" + "-" * 80)
            print(block.content)
            print("-" * 80)

            # Show metadata if available
            if block.block_metadata:
                print(f"\n📋 Metadata: {block.block_metadata}")

            # Show bounding box if available
            if block.bounding_box:
                print(f"\n📐 Bounding Box: {block.bounding_box}")

        else:
            print("❌ Block not found")
            print("\nAvailable blocks with similar IDs:")
            # Search for similar block IDs
            similar_blocks = db.query(ContentBlockDB).filter(
                ContentBlockDB.block_id.like("%mistral%p1%")
            ).limit(10).all()

            for similar in similar_blocks:
                print(f"   - {similar.block_id} ({similar.block_type})")

    finally:
        db.close()


def demonstrate_queries():
    """Demonstrate various content block queries"""
    print("=== Content Block Database Queries ===")

    files = get_test_project_files()
    if not files:
        return

    # Print specific block first
    print_specific_block()

    # Analyze each file
    for file_record in files:
        analyze_content_blocks(file_record)

    # Demonstrate cross-file queries
    print(f"\n🔍 Cross-file analysis:")
    db = SessionLocal()
    try:
        # Count total blocks across all files
        total_blocks = db.query(ContentBlockDB).count()
        print(f"  📊 Total content blocks in database: {total_blocks}")

        # Count by type across all files
        type_query = db.query(ContentBlockDB.block_type, func.count(ContentBlockDB.id)).group_by(ContentBlockDB.block_type).all()
        print("  📈 Block types across all files:")
        for block_type, count in type_query:
            print(f"    - {block_type}: {count}")

        # Find all images across files
        all_images = db.query(ContentBlockDB).filter(ContentBlockDB.block_type == "image").count()
        print(f"  🖼️  Total images across all files: {all_images}")

        # Count parsing services used
        service_query = db.query(ContentBlockDB.parsing_service, func.count(ContentBlockDB.id)).group_by(ContentBlockDB.parsing_service).all()
        print("  🤖 Parsing services used:")
        for service, count in service_query:
            print(f"    - {service}: {count} blocks")

    finally:
        db.close()


if __name__ == "__main__":
    demonstrate_queries()