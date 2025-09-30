"""
Export content blocks to structured markdown files.

This script reads all content blocks from the database and exports them
to organized markdown files in the structure:
parsing_results/file_name/page_i/block_j_content.md
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.content_block_db import ContentBlockDB
from app.models.file import File
from app.models.project import Project
from app.services.content_block_service import ContentBlockService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize settings
settings = get_settings()


class ContentBlockExporter:
    """Service for exporting content blocks to markdown files"""

    def __init__(self, output_base_dir: str = "parsing_results"):
        self.output_base_dir = Path(os.path.dirname(__file__)) / output_base_dir
        self.db = None

    def __enter__(self):
        self.db = SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    def get_test_project(self) -> Project | None:
        """Get the test project created by setup script"""
        project = (
            self.db.query(Project)
            .filter(Project.name == "Report Generation Test")
            .first()
        )
        if not project:
            logger.error(
                "Test project not found. Please run 00_config_and_setup.py first."
            )
            return None
        return project

    def get_parsed_files(self, project_id: str) -> List[File]:
        """Get all files with parsed content blocks"""
        # Get files that have content blocks
        files = (
            self.db.query(File)
            .filter(File.project_id == project_id, File.status == "ready")
            .all()
        )

        # Filter to only files with content blocks
        parsed_files = []
        for file in files:
            block_count = (
                self.db.query(ContentBlockDB)
                .filter(ContentBlockDB.file_id == file.id)
                .count()
            )

            if block_count > 0:
                parsed_files.append(file)
                logger.info(
                    f"Found parsed file: {file.original_name} with {block_count} blocks"
                )

        return parsed_files

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        # Remove file extension and replace problematic characters
        name = os.path.splitext(filename)[0]
        # Replace spaces and special characters with underscores
        sanitized = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        # Remove multiple consecutive underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        return sanitized.strip("_")

    def create_block_markdown(self, block: ContentBlockDB, block_index: int) -> str:
        """Create markdown content for a single block"""
        content = f"""# Content Block {block_index + 1}

## Metadata
- **Block ID**: {block.block_id}
- **Block Type**: {block.block_type}
- **Page Number**: {block.page_number}
- **Position**: {block.position}
- **Parsing Service**: {block.parsing_service}
- **Confidence Score**: {block.confidence_score}
- **Created**: {block.created_at}

## Content

{block.content}
"""

        # Add metadata section if available
        if block.block_metadata:
            content += f"""
## Block Metadata

```json
{block.block_metadata}
```
"""

        # Add bounding box information if available
        if block.bounding_box:
            content += f"""
## Bounding Box

```json
{block.bounding_box}
```
"""
        
        return content
    
    def export_file_blocks(self, file: File) -> bool:
        """Export all blocks for a single file"""
        logger.info(f"Exporting blocks for file: {file.original_name}")
        
        # Get all content blocks for this file, ordered by page and position
        blocks = ContentBlockService.get_content_blocks_for_file(self.db, file.id)
        
        if not blocks:
            logger.warning(f"No blocks found for file: {file.original_name}")
            return False
        
        # Create sanitized file directory name
        sanitized_filename = self.sanitize_filename(file.original_name)
        file_dir = self.output_base_dir / sanitized_filename
        
        # Group blocks by page
        pages: Dict[int, List[ContentBlockDB]] = {}
        for block in blocks:
            page_num = block.page_number or 0
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(block)
        
        # Sort pages and export blocks
        exported_count = 0
        for page_num in sorted(pages.keys()):
            page_blocks = sorted(pages[page_num], key=lambda x: x.position or 0)
            page_dir = file_dir / f"page_{page_num}"
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # Export each block in the page
            for block_index, block in enumerate(page_blocks):
                block_filename = f"block_{block_index + 1:03d}_content.md"
                block_path = page_dir / block_filename
                
                # Create markdown content
                markdown_content = self.create_block_markdown(block, block_index)
                
                # Write to file
                with open(block_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                exported_count += 1
                logger.debug(f"Exported block: {block_path}")
        
        logger.info(f"Exported {exported_count} blocks for {file.original_name}")
        return True
    
    def create_file_summary(self, file: File, blocks: List[ContentBlockDB]) -> str:
        """Create a summary markdown file for the entire file"""
        # Group blocks by page for summary
        pages: Dict[int, List[ContentBlockDB]] = {}
        block_types = set()
        
        for block in blocks:
            page_num = block.page_number or 0
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(block)
            block_types.add(block.block_type)
        
        # Create summary content
        summary = f"""# File Summary: {file.original_name}

## File Information
- **File ID**: {file.id}
- **Original Name**: {file.original_name}
- **Status**: {file.status}
- **Upload Date**: {file.created_at}
- **Total Blocks**: {len(blocks)}
- **Total Pages**: {len(pages)}

## Block Types Found
{chr(10).join(f"- {block_type}" for block_type in sorted(block_types))}

## Page Structure
"""
        
        for page_num in sorted(pages.keys()):
            page_blocks = pages[page_num]
            block_type_counts = {}
            for block in page_blocks:
                block_type_counts[block.block_type] = block_type_counts.get(block.block_type, 0) + 1
            
            summary += f"""
### Page {page_num}
- **Total Blocks**: {len(page_blocks)}
- **Block Types**: {', '.join(f"{bt}({count})" for bt, count in sorted(block_type_counts.items()))}
"""
        
        summary += f"""
## Navigation
Each page is organized in its own directory:
```
{self.sanitize_filename(file.original_name)}/
├── README.md (this file)
"""
        
        for page_num in sorted(pages.keys()):
            summary += f"├── page_{page_num}/\n"
            page_blocks = sorted(pages[page_num], key=lambda x: x.position or 0)
            for i, _ in enumerate(page_blocks):
                summary += f"│   ├── block_{i + 1:03d}_content.md\n"
        
        summary += "```\n"
        
        return summary
    
    def export_all_files(self) -> bool:
        """Export blocks for all files in the test project"""
        # Get test project
        project = self.get_test_project()
        if not project:
            return False
        
        logger.info(f"Using project: {project.name} (ID: {project.id})")
        
        # Get parsed files
        parsed_files = self.get_parsed_files(str(project.id))
        
        if not parsed_files:
            logger.error("No parsed files found in the database")
            logger.info("Please run 02_read_and_parse_file.py first to parse documents")
            return False
        
        logger.info(f"Found {len(parsed_files)} parsed files to export")
        
        # Create output directory
        self.output_base_dir.mkdir(exist_ok=True)
        
        # Export each file
        success_count = 0
        for file in parsed_files:
            try:
                # Export blocks
                if self.export_file_blocks(file):
                    # Create file summary
                    blocks = ContentBlockService.get_content_blocks_for_file(self.db, file.id)
                    summary_content = self.create_file_summary(file, blocks)
                    
                    sanitized_filename = self.sanitize_filename(file.original_name)
                    summary_path = self.output_base_dir / sanitized_filename / "README.md"
                    
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write(summary_content)
                    
                    success_count += 1
                    logger.info(f"✅ Successfully exported: {file.original_name}")
                else:
                    logger.error(f"❌ Failed to export: {file.original_name}")
            
            except Exception as e:
                logger.error(f"❌ Error exporting {file.original_name}: {e}")
        
        # Create overall index
        self.create_overall_index(parsed_files)
        
        logger.info(f"Export completed: {success_count}/{len(parsed_files)} files exported successfully")
        logger.info(f"Output directory: {self.output_base_dir.absolute()}")
        
        return success_count > 0
    
    def create_overall_index(self, files: List[File]) -> None:
        """Create an overall index file for all exported content"""
        index_content = f"""# Parsing Results Index

This directory contains exported content blocks from parsed documents.

## Export Information
- **Export Date**: {os.environ.get('TZ', 'UTC')} 
- **Total Files**: {len(files)}
- **Export Script**: 04_export_content_blocks.py

## File Structure
Each file is organized in its own directory with the following structure:
```
parsing_results/
├── README.md (this file)
"""
        
        for file in files:
            sanitized_name = self.sanitize_filename(file.original_name)
            index_content += f"├── {sanitized_name}/\n"
            index_content += f"│   ├── README.md (file summary)\n"
            index_content += f"│   ├── page_0/\n"
            index_content += f"│   │   ├── block_001_content.md\n"
            index_content += f"│   │   └── ...\n"
            index_content += f"│   └── ...\n"
        
        index_content += """```

## Files Exported
"""
        
        for file in files:
            sanitized_name = self.sanitize_filename(file.original_name)
            index_content += f"- **{file.original_name}** → `{sanitized_name}/`\n"
        
        index_content += """
## Usage
1. Navigate to the specific file directory
2. Read the README.md for file summary and structure
3. Browse page directories to access individual content blocks
4. Each block contains metadata and extracted content

## Block Structure
Each block markdown file contains:
- Block metadata (ID, type, page, position, etc.)
- Extracted content
- Parsing service information
- Confidence scores
- Bounding box data (if available)
"""
        
        index_path = self.output_base_dir / "README.md"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        logger.info(f"Created overall index: {index_path}")


def main():
    """Main execution function"""
    print("=" * 60)
    print("📁 CONTENT BLOCKS EXPORT TO MARKDOWN")
    print("=" * 60)
    print()
    
    try:
        with ContentBlockExporter() as exporter:
            success = exporter.export_all_files()
            
            if success:
                print("✅ Export completed successfully!")
                print(f"📂 Output directory: {exporter.output_base_dir.absolute()}")
                print()
                print("📋 Next steps:")
                print("1. Browse the parsing_results/ directory")
                print("2. Check individual file README.md files for summaries")
                print("3. Navigate page directories to view content blocks")
            else:
                print("❌ Export failed!")
                print("Check the logs for more details")
    
    except Exception as e:
        logger.error(f"Unexpected error during export: {e}")
        print("❌ Export failed due to unexpected error")
        return False
    
    return True


if __name__ == "__main__":
    main()
