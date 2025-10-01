"""
Schema service layer
Business logic for schema CRUD operations
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.schema import Schema
from app.utils import CRUDRepository, QueryBuilder, FilterOperator, SortOrder
from app.schemas.schema_schemas import SchemaCreate, SchemaUpdate


class SchemaService:
    """Service class for schema business logic"""
    
    def __init__(self):
        """Initialize schema service with repository"""
        self.repo = CRUDRepository(Schema)
    
    def get_all_schemas(
        self,
        db: Session,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Schema], int]:
        """Get all schemas for a user (no filtering, just user's schemas)"""
        query = QueryBuilder(Schema, db)
        
        # Only get current user's schemas
        query.filter("user_id", user_id)
        
        # Sort by most recent first
        query.sort("created_at", SortOrder.DESC)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        schemas = query.offset(skip).limit(limit).all()
        
        return schemas, total
    
    def get_templates(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Schema], int]:
        """Get all template schemas"""
        query = (
            QueryBuilder(Schema, db)
            .filter("is_template", True)
            .sort("name", SortOrder.ASC)
        )
        
        total = query.count()
        schemas = query.offset(skip).limit(limit).all()
        
        return schemas, total
    
    def get_schema_by_id(
        self,
        db: Session,
        schema_id: UUID,
        user_id: Optional[str] = None
    ) -> Optional[Schema]:
        """Get a schema by ID, optionally checking user ownership"""
        schema = self.repo.get_by_id(db, schema_id)
        
        if not schema:
            return None
        
        # If user_id provided, verify ownership or template
        if user_id and schema.user_id != user_id and not schema.is_template:
            return None
        
        return schema
    
    def create_schema(
        self,
        db: Session,
        user_id: str,
        schema_data: SchemaCreate
    ) -> Schema:
        """Create a new schema"""
        # Check if cloning from template
        if schema_data.base_schema_id:
            base_schema = self.get_schema_by_id(db, schema_data.base_schema_id, user_id)
            if not base_schema:
                raise ValueError("Base schema not found or not accessible")
        
        # Create schema
        new_schema = self.repo.create(db, {
            "user_id": user_id,
            "name": schema_data.name,
            "description": schema_data.description,
            "schema_definition": schema_data.schema_definition,
            "base_schema_id": schema_data.base_schema_id,
            "is_template": schema_data.is_template,
            "version": 1
        })
        
        return new_schema
    
    def update_schema(
        self,
        db: Session,
        schema_id: UUID,
        user_id: str,
        schema_data: SchemaUpdate
    ) -> Optional[Schema]:
        """Update an existing schema"""
        # Verify strict ownership - only allow updating user's own schemas
        schema = self.get_schema_by_id(db, schema_id, user_id)
        if not schema or schema.user_id != user_id:
            return None
        
        # Prepare update data
        update_data = schema_data.model_dump(exclude_unset=True)
        
        # Update schema
        updated_schema = self.repo.update(db, schema_id, update_data)
        
        return updated_schema
    
    def delete_schema(
        self,
        db: Session,
        schema_id: UUID,
        user_id: str
    ) -> bool:
        """Delete a schema"""
        # Verify strict ownership - only allow deleting user's own schemas
        schema = self.get_schema_by_id(db, schema_id, user_id)
        if not schema or schema.user_id != user_id:
            return False
        
        # Delete schema
        return self.repo.delete(db, schema_id)
    
    def clone_schema(
        self,
        db: Session,
        schema_id: UUID,
        user_id: str,
        new_name: str,
        new_description: Optional[str] = None
    ) -> Optional[Schema]:
        """Clone an existing schema"""
        # Get source schema
        source_schema = self.get_schema_by_id(db, schema_id, user_id)
        if not source_schema:
            return None
        
        # Create cloned schema
        cloned_schema = self.repo.create(db, {
            "user_id": user_id,
            "name": new_name,
            "description": new_description or source_schema.description,
            "schema_definition": source_schema.schema_definition,
            "base_schema_id": schema_id,
            "is_template": False,
            "version": 1
        })
        
        return cloned_schema
    
    def search_schemas(
        self,
        db: Session,
        user_id: str,
        search_term: str,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Schema], int]:
        """Search schemas by name or description"""
        query = (
            QueryBuilder(Schema, db)
            .filter_or([
                ("user_id", user_id, FilterOperator.EQUALS),
                ("is_template", True, FilterOperator.EQUALS),
            ])
            .filter_or([
                ("name", f"%{search_term}%", FilterOperator.ILIKE),
                ("description", f"%{search_term}%", FilterOperator.ILIKE),
            ])
            .sort("created_at", SortOrder.DESC)
        )
        
        total = query.count()
        schemas = query.offset(skip).limit(limit).all()
        
        return schemas, total
