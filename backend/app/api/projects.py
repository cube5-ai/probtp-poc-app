"""
Project management API endpoints (create, delete)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.utils import get_db_session
from app.services.project_service import ProjectService
from app.schemas.project_schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectListResponse
)

router = APIRouter(prefix="/projects", tags=["projects"])
project_service = ProjectService()


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project and assign the creator as owner"
)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
) -> ProjectResponse:
    """Create a new project and add current user as owner"""
    try:
        project = project_service.create_project(db, user_id, project_data)
        return project
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List user projects",
    description="Get all projects where the current user is a member"
)
def list_user_projects(
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
) -> list[ProjectResponse]:
    """List all projects where the current user is a member"""
    projects, total = project_service.get_user_projects(db, user_id)
    return projects


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project by ID",
    description="Get a specific project if user is a member"
)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
) -> ProjectResponse:
    """Get a specific project by ID"""
    project = project_service.get_project_by_id(db, project_id, user_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized"
        )
    
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete a project (and its files/members) if requester is owner"
)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id)
) -> None:
    """Delete project if current user is owner"""
    deleted = project_service.delete_project(db, project_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized"
        )
    
    return None


