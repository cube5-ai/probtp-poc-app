"""
Content block service for managing parsed document content blocks
"""
import logging
import uuid

from sqlalchemy.orm import Session

from app.models.content_block import ContentBlock
from app.models.content_block_db import ContentBlockDB
from app.models.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


class ContentBlockService:
    """Service for managing content blocks in the database"""

    @staticmethod
    def save_parsed_document_blocks(
        db: Session,
        file_id: uuid.UUID,
        parsed_document: ParsedDocument
    ) -> list[ContentBlockDB]:
        """
        Save all content blocks from a parsed document to the database.

        Args:
            db: Database session
            file_id: ID of the file these blocks belong to
            parsed_document: Parsed document containing content blocks

        Returns:
            List of saved ContentBlockDB instances

        Raises:
            Exception: If database operation fails
        """
        try:
            saved_blocks = []

            # Convert each content block to database model and save
            for block in parsed_document.content_blocks:
                db_block = block.to_db_model(
                    file_id=file_id,
                    parsing_service=parsed_document.parsing_service,
                    document_id=parsed_document.document_id
                )

                db.add(db_block)
                saved_blocks.append(db_block)

            # Commit all blocks at once
            db.commit()

            logger.info(f"Saved {len(saved_blocks)} content blocks for file {file_id}", extra={
                "file_id": str(file_id),
                "document_id": parsed_document.document_id,
                "parsing_service": parsed_document.parsing_service,
                "blocks_count": len(saved_blocks)
            })

            return saved_blocks

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save content blocks for file {file_id}: {e}", extra={
                "file_id": str(file_id),
                "document_id": parsed_document.document_id,
                "error": str(e)
            })
            raise

    @staticmethod
    def get_content_blocks_for_file(
        db: Session,
        file_id: uuid.UUID
    ) -> list[ContentBlockDB]:
        """
        Get all content blocks for a file, ordered by page and position.

        Args:
            db: Database session
            file_id: ID of the file

        Returns:
            List of ContentBlockDB instances ordered by page and position
        """
        return (
            db.query(ContentBlockDB)
            .filter(ContentBlockDB.file_id == file_id)
            .order_by(ContentBlockDB.page_number.asc(), ContentBlockDB.position.asc())
            .all()
        )

    @staticmethod
    def get_content_blocks_for_page(
        db: Session,
        file_id: uuid.UUID,
        page_number: int
    ) -> list[ContentBlockDB]:
        """
        Get all content blocks for a specific page, ordered by position.

        Args:
            db: Database session
            file_id: ID of the file
            page_number: Page number

        Returns:
            List of ContentBlockDB instances ordered by position
        """
        return (
            db.query(ContentBlockDB)
            .filter(
                ContentBlockDB.file_id == file_id,
                ContentBlockDB.page_number == page_number
            )
            .order_by(ContentBlockDB.position.asc())
            .all()
        )

    @staticmethod
    def get_blocks_by_type(
        db: Session,
        file_id: uuid.UUID,
        block_type: str
    ) -> list[ContentBlockDB]:
        """
        Get all content blocks of a specific type for a file.

        Args:
            db: Database session
            file_id: ID of the file
            block_type: Type of blocks to retrieve (text, image, table, heading, list)

        Returns:
            List of ContentBlockDB instances of the specified type
        """
        return (
            db.query(ContentBlockDB)
            .filter(
                ContentBlockDB.file_id == file_id,
                ContentBlockDB.block_type == block_type
            )
            .order_by(ContentBlockDB.page_number.asc(), ContentBlockDB.position.asc())
            .all()
        )

    @staticmethod
    def delete_content_blocks_for_file(db: Session, file_id: uuid.UUID) -> int:
        """
        Delete all content blocks for a file.

        Args:
            db: Database session
            file_id: ID of the file

        Returns:
            Number of blocks deleted
        """
        try:
            deleted_count = (
                db.query(ContentBlockDB)
                .filter(ContentBlockDB.file_id == file_id)
                .delete()
            )

            db.commit()

            logger.info(f"Deleted {deleted_count} content blocks for file {file_id}", extra={
                "file_id": str(file_id),
                "deleted_count": deleted_count
            })

            return deleted_count

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete content blocks for file {file_id}: {e}", extra={
                "file_id": str(file_id),
                "error": str(e)
            })
            raise

    @staticmethod
    def convert_to_api_models(db_blocks: list[ContentBlockDB]) -> list[ContentBlock]:
        """
        Convert database models to API models.

        Args:
            db_blocks: List of ContentBlockDB instances

        Returns:
            List of ContentBlock instances for API responses
        """
        return [ContentBlock.from_db_model(db_block) for db_block in db_blocks]
