"""
Pydantic schemas for project API request/response models
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request schema for creating a project"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ProjectResponse(BaseModel):
    """Response schema for project data"""
    id: UUID = Field(..., description="Project identifier")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    created_by: str = Field(..., description="User who created the project (Firebase UID)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    file_count: int = Field(0, description="Number of files in the project")
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Response schema for project list"""
    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")

