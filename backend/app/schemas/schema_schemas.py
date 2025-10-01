"""
Pydantic schemas for Schema model
Request/Response validation for schema endpoints
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4


class SchemaBase(BaseModel):
    """Base schema with common fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Schema name")
    description: Optional[str] = Field(None, description="Schema description")
    schema_definition: Dict[str, Any] = Field(
        ..., 
        description="JSON Schema definition", 
        serialization_alias="schemaDefinition",
        validation_alias="schemaDefinition"
    )
    
    class Config:
        populate_by_name = True


class SchemaCreate(SchemaBase):
    """Schema for creating a new schema"""
    base_schema_id: Optional[UUID4] = Field(None, description="Base template schema ID if cloning", validation_alias="baseSchemaId")
    is_template: bool = Field(False, description="Whether this is a template schema", validation_alias="isTemplate")
    
    class Config:
        populate_by_name = True


class SchemaUpdate(BaseModel):
    """Schema for updating an existing schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Schema name")
    description: Optional[str] = Field(None, description="Schema description")
    schema_definition: Optional[Dict[str, Any]] = Field(None, description="JSON Schema definition", validation_alias="schemaDefinition")
    
    class Config:
        populate_by_name = True


class SchemaResponse(SchemaBase):
    """Schema response model"""
    id: UUID4 = Field(..., description="Schema unique identifier")
    user_id: str = Field(..., description="User ID who owns the schema", serialization_alias="userId")
    base_schema_id: Optional[UUID4] = Field(None, description="Base template schema ID", serialization_alias="baseSchemaId")
    is_template: bool = Field(..., description="Whether this is a template", serialization_alias="isTemplate")
    version: int = Field(..., description="Schema version number")
    created_at: datetime = Field(..., description="Creation timestamp", serialization_alias="createdAt")
    updated_at: datetime = Field(..., description="Last update timestamp", serialization_alias="updatedAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class SchemaListResponse(BaseModel):
    """Response for listing schemas"""
    schemas: list[SchemaResponse] = Field(..., description="List of schemas")
    total: int = Field(..., description="Total number of schemas")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")


class SchemaCloneRequest(BaseModel):
    """Request to clone a schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Name for cloned schema")
    description: Optional[str] = Field(None, description="Description for cloned schema")
