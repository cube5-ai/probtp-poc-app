"""
Project service layer
Business logic for project CRUD operations
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.utils import CRUDRepository
from app.schemas.project_schemas import ProjectCreate


class ProjectService:
    """Service class for project business logic"""
    
    def __init__(self):
        """Initialize project service with repository"""
        self.project_repo = CRUDRepository(Project)
        self.member_repo = CRUDRepository(ProjectMember)
    
    def create_project(
        self,
        db: Session,
        user_id: str,
        project_data: ProjectCreate
    ) -> Project:
        """Create a new project and add creator as owner"""
        # Create project
        project = self.project_repo.create(db, {
            "name": project_data.name,
            "description": project_data.description,
            "created_by": user_id,
        })
        
        # Add creator as owner
        self.member_repo.create(db, {
            "project_id": project.id,
            "user_id": user_id,
            "role": "owner",
            "added_by": user_id,
        })
        
        return project
    
    def get_user_projects(
        self,
        db: Session,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Project], int]:
        """Get all projects where the user is a member with file counts"""
        from sqlalchemy import func
        from app.models.file import File
        
        # Use direct SQLAlchemy query for join operations with file count
        query = (
            db.query(
                Project,
                func.count(File.id).label('file_count')
            )
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .outerjoin(File, (File.project_id == Project.id) & (File.deleted_at.is_(None)))
            .filter(ProjectMember.user_id == user_id)
            .group_by(Project.id)
            .order_by(Project.created_at.desc())
        )
        
        total = query.count()
        results = query.offset(skip).limit(limit).all()
        
        # Add file_count attribute to each project
        projects = []
        for project, file_count in results:
            project.file_count = file_count
            projects.append(project)
        
        return projects, total
    
    def get_project_by_id(
        self,
        db: Session,
        project_id: UUID,
        user_id: Optional[str] = None
    ) -> Optional[Project]:
        """Get a project by ID, optionally checking user membership"""
        from sqlalchemy import func
        from app.models.file import File
        
        # Query project with file count
        result = (
            db.query(
                Project,
                func.count(File.id).label('file_count')
            )
            .outerjoin(File, (File.project_id == Project.id) & (File.deleted_at.is_(None)))
            .filter(Project.id == project_id)
            .group_by(Project.id)
            .first()
        )
        
        if not result:
            return None
        
        project, file_count = result
        
        # If user_id provided, verify membership
        if user_id:
            membership = db.query(ProjectMember).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id
            ).first()
            
            if not membership:
                return None
        
        # Add file_count attribute to project
        project.file_count = file_count
        return project
    
    def is_project_owner(
        self,
        db: Session,
        project_id: UUID,
        user_id: str
    ) -> bool:
        """Check if user is owner of a project"""
        membership = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role == "owner"
        ).first()
        
        return membership is not None
    
    def delete_project(
        self,
        db: Session,
        project_id: UUID,
        user_id: str
    ) -> bool:
        """Delete a project if user is owner"""
        # Check ownership
        if not self.is_project_owner(db, project_id, user_id):
            return False
        
        # Verify project exists
        project = self.project_repo.get_by_id(db, project_id)
        if not project:
            return False
        
        # Delete project (cascades to members and files)
        return self.project_repo.delete(db, project_id)

