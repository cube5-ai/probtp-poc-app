"""
Schema API endpoints
CRUD operations for user-defined schemas
"""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.utils import get_db_session
from app.services.schema_service import SchemaService
from app.services.ai_schema_service import AISchemaService
from app.schemas.schema_schemas import (
    SchemaCreate,
    SchemaUpdate,
    SchemaResponse,
    SchemaListResponse,
    SchemaCloneRequest,
    SchemaRefineRequest,
    SchemaRefineResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schemas", tags=["schemas"])
schema_service = SchemaService()
ai_schema_service = AISchemaService()


@router.get("/", response_model=SchemaListResponse)
def list_schemas(
    search: Optional[str] = Query(None, description="Search term for name/description"),
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """List all schemas for the current user (returns all, no pagination)"""
    # Get all user's schemas (no pagination, no filtering)
    if search:
        schemas, total = schema_service.search_schemas(
            db, user_id, search, skip=0, limit=10000
        )
    else:
        schemas, total = schema_service.get_all_schemas(
            db, user_id, skip=0, limit=10000
        )
    
    return {
        "schemas": schemas,
        "total": len(schemas),
        "page": 1,
        "page_size": len(schemas)
    }


@router.get("/templates", response_model=SchemaListResponse)
def list_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db_session)
):
    """List all template schemas"""
    skip = (page - 1) * page_size
    schemas, total = schema_service.get_templates(db, skip, page_size)
    
    return {
        "schemas": schemas,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{schema_id}", response_model=SchemaResponse)
def get_schema(
    schema_id: UUID,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """Get a specific schema by ID"""
    print(f"Getting schema {schema_id} for user {user_id}")
    
    # For development: allow reading any schema, but ownership info is preserved
    schema = schema_service.get_schema_by_id(db, schema_id)
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    print(f"Schema found, owned by: {schema.user_id}")
    return schema


@router.post("/", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
def create_schema(
    schema_data: SchemaCreate,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """Create a new schema"""
    try:
        schema = schema_service.create_schema(db, user_id, schema_data)
        return schema
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{schema_id}", response_model=SchemaResponse)
def update_schema(
    schema_id: UUID,
    schema_data: SchemaUpdate,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """Update an existing schema"""
    print(f"Updating schema {schema_id} for user {user_id}")
    
    # Check if schema exists and show ownership
    existing_schema = schema_service.get_schema_by_id(db, schema_id)
    if existing_schema:
        print(f"Schema exists, owned by: {existing_schema.user_id}")
        print(f"User trying to update: {user_id}")
        print(f"Ownership match: {existing_schema.user_id == user_id}")
    
    schema = schema_service.update_schema(db, schema_id, user_id, schema_data)
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found or unauthorized"
        )
    
    return schema


@router.delete("/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schema(
    schema_id: UUID,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """Delete a schema"""
    deleted = schema_service.delete_schema(db, schema_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found or unauthorized"
        )
    
    return None


@router.post("/{schema_id}/clone", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
def clone_schema(
    schema_id: UUID,
    clone_data: SchemaCloneRequest,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
):
    """Clone an existing schema"""
    cloned_schema = schema_service.clone_schema(
        db, schema_id, user_id, clone_data.name, clone_data.description
    )
    
    if not cloned_schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    return cloned_schema


@router.post("/refine", response_model=SchemaRefineResponse)
def refine_schema(
    refine_data: SchemaRefineRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Refine a schema using AI based on user instruction"""
    logger.info("=" * 80)
    logger.info(f"Refine schema endpoint called by user: {user_id}")
    logger.info(f"Request data: {refine_data.model_dump()}")
    
    try:
        logger.info("Calling AI schema service...")
        refined_schema = ai_schema_service.refine_schema(
            refine_data.schema_definition,
            refine_data.instruction
        )
        
        logger.info(f"AI service returned refined schema with {len(refined_schema.get('properties', {}))} properties")
        
        response = SchemaRefineResponse(refined_schema=refined_schema)
        logger.info(f"Response object created")
        logger.info(f"Response.model_dump(): {response.model_dump()}")
        logger.info(f"Response.model_dump(by_alias=True): {response.model_dump(by_alias=True)}")
        logger.info("=" * 80)
        return response
        
    except ValueError as e:
        logger.error(f"ValueError in schema refinement: {e}")
        logger.error("=" * 80)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in schema refinement: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema refinement failed: {str(e)}"
        )
