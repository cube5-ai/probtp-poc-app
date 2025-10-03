"""
File upload API endpoints
"""
import time
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.api.errors import FileUploadError, UploadErrors
from app.api.api_models import (
    FileConfirmRequest,
    FileConfirmResponse,
    FileListItem,
    FileListResponse,
    FileStatusResponse,
    FileUploadRequest,
    FileUploadResponse,
    PaginationInfo,
    UserInfo,
)
from app.core.config import get_settings
from app.core.logging import FileUploadLogger, log_exception
from app.models.file import File
from app.models.project import Project
from app.services.auth_service import AuthorizationService
from app.services.storage_service import StorageService

router = APIRouter()
settings = get_settings()


@router.post(
    "/projects/{project_id}/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize file upload",
    description="Create a new file upload and get signed URL for direct upload to cloud storage"
)
async def initialize_file_upload(
    project_id: UUID,
    request: FileUploadRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> FileUploadResponse:
    """Initialize file upload and return signed URL"""
    start_time = time.time()

    try:
        # Check if user can upload to this project
        can_upload = await AuthorizationService.can_upload_file(
            db, current_user_id, project_id
        )
        if not can_upload:
            raise UploadErrors.NO_PERMISSION

        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise UploadErrors.INVALID_PROJECT

        # Create file record
        file_id = uuid.uuid4()
        storage_service = StorageService()

        # Generate signed upload URL
        upload_url, storage_path = storage_service.generate_upload_url(
            project_id=str(project_id),
            file_id=str(file_id),
            content_type='application/pdf',
            expiration_minutes=settings.upload_url_expiration_minutes
        )

        # Create file record in database
        new_file = File(
            id=file_id,
            project_id=project_id,
            original_name=request.filename,
            storage_path=storage_path,
            file_size=request.file_size,
            mime_type='application/pdf',
            status='pending',
            upload_url=upload_url,
            upload_url_expires_at=datetime.utcnow() + timedelta(
                minutes=settings.upload_url_expiration_minutes
            ),
            uploaded_by=current_user_id
        )

        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        # Log upload initiation
        FileUploadLogger.log_upload_initiated(
            user_id=current_user_id,
            project_id=str(project_id),
            file_name=request.filename,
            file_size=request.file_size,
            file_id=str(file_id)
        )

        return FileUploadResponse(
            upload_id=new_file.id,
            upload_url=upload_url,
            upload_method="PUT",
            expires_at=new_file.upload_url_expires_at,
            max_file_size=settings.max_file_size_mb * 1024 * 1024
        )

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, project_id=str(project_id))
        raise UploadErrors.UPLOAD_FAILED


@router.post(
    "/projects/{project_id}/files/{file_id}/confirm",
    response_model=FileConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm file upload completion",
    description="Mark file upload as completed and ready for use"
)
async def confirm_file_upload(
    project_id: UUID,
    file_id: UUID,
    request: FileConfirmRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> FileConfirmResponse:
    """Confirm file upload completion"""
    start_time = time.time()

    try:
        # Get file record
        file_record = db.query(File).filter(
            and_(
                File.id == file_id,
                File.project_id == project_id,
                File.uploaded_by == current_user_id,
                File.deleted_at.is_(None)
            )
        ).first()

        if not file_record:
            raise UploadErrors.FILE_NOT_FOUND

        # Check if upload URL has expired
        if file_record.upload_expired:
            raise UploadErrors.UPLOAD_EXPIRED

        # Check file status
        if file_record.status not in ['pending', 'uploading']:
            raise UploadErrors.INVALID_FILE_STATUS

        # Verify file exists in cloud storage
        storage_service = StorageService()
        if not storage_service.file_exists(file_record.storage_path):
            file_record.mark_as_failed("File not found in cloud storage")
            db.commit()
            raise FileUploadError("File upload verification failed", 400)

        # Update MD5 hash if provided
        if request.md5_hash:
            file_record.md5_hash = request.md5_hash

        # Mark file as ready
        file_record.mark_as_ready()
        file_record.upload_url = None  # Clear signed URL for security
        file_record.upload_url_expires_at = None

        db.commit()

        # Log upload completion
        duration = time.time() - start_time
        FileUploadLogger.log_upload_completed(
            user_id=current_user_id,
            file_id=str(file_id),
            project_id=str(project_id),
            duration_seconds=duration,
            file_size=file_record.file_size,
            storage_path=file_record.storage_path
        )

        return FileConfirmResponse(
            file_id=file_record.id,
            status=file_record.status,
            message="File uploaded successfully"
        )

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, file_id=str(file_id))
        raise UploadErrors.UPLOAD_FAILED


@router.get(
    "/projects/{project_id}/files",
    response_model=FileListResponse,
    status_code=status.HTTP_200_OK,
    summary="List project files",
    description="Get paginated list of files in a project with download URLs"
)
async def list_project_files(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, description="Filter by file status"),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> FileListResponse:
    """List files in a project with pagination"""
    try:
        # Check if user has access to project
        has_access = await AuthorizationService.check_project_permission(
            db, current_user_id, project_id
        )
        if not has_access:
            raise UploadErrors.NO_PERMISSION

        # Build query
        query = db.query(File).filter(
            and_(
                File.project_id == project_id,
                File.deleted_at.is_(None)
            )
        )

        # Apply status filter if provided
        if status_filter:
            query = query.filter(File.status == status_filter)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        files = query.order_by(desc(File.created_at)).offset(
            (page - 1) * limit
        ).limit(limit).all()

        # Generate download URLs for ready files
        storage_service = StorageService()
        file_items = []

        for file in files:
            download_url = None
            if file.is_ready:
                try:
                    download_url = storage_service.generate_download_url(
                        file.storage_path,
                        settings.download_url_expiration_minutes
                    )
                except Exception:
                    # Log error but don't fail the entire request
                    pass

            file_items.append(FileListItem(
                id=file.id,
                original_name=file.original_name,
                file_size=file.file_size,
                status=file.status,
                uploaded_by=UserInfo(
                    id=file.uploaded_by,
                    email="user@example.com",  # TODO: Get from Firebase
                    name="User Name"  # TODO: Get from Firebase
                ),
                created_at=file.created_at,
                download_url=download_url
            ))

        # Calculate pagination info
        pages = (total + limit - 1) // limit

        return FileListResponse(
            files=file_items,
            pagination=PaginationInfo(
                page=page,
                size=limit,
                total=total,
                pages=pages
            )
        )

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, project_id=str(project_id))
        raise UploadErrors.DATABASE_ERROR


@router.get(
    "/projects/{project_id}/files/{file_id}",
    response_model=FileListItem,
    status_code=status.HTTP_200_OK,
    summary="Get file details",
    description="Get details of a specific file in a project"
)
async def get_file_details(
    project_id: UUID,
    file_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> FileListItem:
    """Get details of a specific file"""
    try:
        # Check if user has access to project
        has_access = await AuthorizationService.check_project_permission(
            db, current_user_id, project_id
        )
        if not has_access:
            raise UploadErrors.NO_PERMISSION

        # Get file record
        file_record = db.query(File).filter(
            and_(
                File.id == file_id,
                File.project_id == project_id,
                File.deleted_at.is_(None)
            )
        ).first()

        if not file_record:
            raise UploadErrors.FILE_NOT_FOUND

        # Generate download URL if file is ready
        download_url = None
        if file_record.is_ready:
            try:
                storage_service = StorageService()
                download_url = storage_service.generate_download_url(
                    file_record.storage_path,
                    settings.download_url_expiration_minutes
                )
            except Exception:
                # Log error but don't fail the entire request
                pass

        return FileListItem(
            id=file_record.id,
            original_name=file_record.original_name,
            file_size=file_record.file_size,
            status=file_record.status,
            uploaded_by=UserInfo(
                id=file_record.uploaded_by,
                email="user@example.com",  # TODO: Get from Firebase
                name="User Name"  # TODO: Get from Firebase
            ),
            created_at=file_record.created_at,
            download_url=download_url
        )

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, context={"project_id": str(project_id), "file_id": str(file_id)})
        raise UploadErrors.DATABASE_ERROR


@router.get(
    "/files/{file_id}/status",
    response_model=FileStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get file status",
    description="Check the current status of a file upload"
)
async def get_file_status(
    file_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> FileStatusResponse:
    """Get current file status"""
    try:
        # Get file record
        file_record = db.query(File).filter(
            and_(
                File.id == file_id,
                File.deleted_at.is_(None)
            )
        ).first()

        if not file_record:
            raise UploadErrors.FILE_NOT_FOUND

        # Check if user can view this file
        can_view = await AuthorizationService.can_view_file(
            db, current_user_id, file_id
        )
        if not can_view:
            raise UploadErrors.NO_PERMISSION

        # Calculate progress (simplified - could be enhanced with actual progress tracking)
        progress = None
        if file_record.status == 'uploading':
            progress = 50  # Placeholder progress
        elif file_record.status == 'ready':
            progress = 100

        return FileStatusResponse(
            file_id=file_record.id,
            status=file_record.status,
            progress=progress,
            updated_at=file_record.updated_at,
            error_message=file_record.error_message
        )

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, file_id=str(file_id))
        raise UploadErrors.DATABASE_ERROR


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete file",
    description="Soft delete a file (mark as deleted without removing from storage)"
)
async def delete_file(
    file_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> None:
    """Delete a file (soft delete)"""
    try:
        # Check if user can delete this file
        can_delete = await AuthorizationService.can_delete_file(
            db, current_user_id, file_id
        )
        if not can_delete:
            raise UploadErrors.NO_PERMISSION

        # Get file record
        file_record = db.query(File).filter(
            and_(
                File.id == file_id,
                File.deleted_at.is_(None)
            )
        ).first()

        if not file_record:
            raise UploadErrors.FILE_NOT_FOUND

        # Soft delete the file
        file_record.soft_delete()
        db.commit()

        # Log file deletion
        FileUploadLogger.log_file_deleted(
            user_id=current_user_id,
            file_id=str(file_id),
            project_id=str(file_record.project_id),
            file_name=file_record.original_name,
            storage_path=file_record.storage_path
        )

        # Note: We don't delete from cloud storage immediately for safety
        # This could be done via a background job or cleanup process

    except FileUploadError:
        raise
    except Exception as e:
        log_exception(e, user_id=current_user_id, file_id=str(file_id))
        raise UploadErrors.DATABASE_ERROR
