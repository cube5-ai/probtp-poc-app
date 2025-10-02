"""
Project management API endpoints (create, delete)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.api.errors import FileUploadError, UploadErrors
from app.api.api_models import ProjectCreateRequest, ProjectResponse
from app.core.logging import log_exception
from app.models.project import Project
from app.models.project_member import ProjectMember

router = APIRouter()


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project and assign the creator as owner"
)
async def create_project(
    request: ProjectCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> ProjectResponse:
    """Create a new project and add current user as owner."""
    try:
        # Create project
        project = Project(
            name=request.name,
            description=request.description,
            created_by=current_user_id,
        )
        db.add(project)
        db.flush()

        # Add creator as owner
        owner_membership = ProjectMember(
            project_id=project.id,
            user_id=current_user_id,
            role="owner",
            added_by=current_user_id,
        )
        db.add(owner_membership)
        db.commit()
        db.refresh(project)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            created_by=project.created_by,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
    except Exception as e:
        db.rollback()
        log_exception(e, user_id=current_user_id)
        raise UploadErrors.DATABASE_ERROR


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List user projects",
    description="Get all projects where the current user is a member"
)
async def list_user_projects(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> list[ProjectResponse]:
    """List all projects where the current user is a member."""
    try:
        # Get all projects where user is a member
        user_projects = (
            db.query(Project)
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .filter(ProjectMember.user_id == current_user_id)
            .order_by(Project.created_at.desc())
            .all()
        )

        return [
            ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                created_by=project.created_by,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project in user_projects
        ]

    except Exception as e:
        log_exception(e, user_id=current_user_id)
        raise UploadErrors.DATABASE_ERROR


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete a project (and its files/members) if requester is owner"
)
async def delete_project(
    project_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> None:
    """Delete project if current user is owner."""
    try:
        # Check ownership
        membership = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user_id,
            ProjectMember.role == "owner",
        ).first()

        if not membership:
            raise UploadErrors.NO_PERMISSION

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise UploadErrors.INVALID_PROJECT

        # Deleting the project cascades to files and members
        db.delete(project)
        db.commit()
        return None
    except FileUploadError:
        raise
    except Exception as e:
        db.rollback()
        log_exception(e, user_id=current_user_id, context={"project_id": str(project_id)})
        raise UploadErrors.DATABASE_ERROR


