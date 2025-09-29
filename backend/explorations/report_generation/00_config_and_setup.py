"""
Configuration and setup script for report generation exploration
- Establish the config and services access 
- Populate the schema databases, enable pgvector extension with CREATE EXTENSION IF NOT EXISTS "vector";


Run the following command to set the GOOGLE_APPLICATION_CREDENTIALS environment variable:
!export GOOGLE_APPLICATION_CREDENTIALS=/Users/jb/Documents/Work/Pro/Cube5/probtp-poc-app/backend-sa-key.json

probtp-poc-prod:europe-west9:probtp-poc-db-prod

"""
import os
import sys
import uuid
from datetime import datetime, timezone

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, create_tables
from app.models.file import File
from app.models.project import Project
from app.services.auth_service import FirebaseAuthService
from app.services.storage_service import StorageService

# Initialize configuration and services
settings = get_settings()
storage_service = StorageService()

def setup_database():
    """Create database tables if they don't exist"""
    print("Setting up database tables...")
    create_tables()
    print("✓ Database tables created/verified")

def setup_test_project():
    """Create a test project for report generation experiments"""
    db = SessionLocal()
    try:
        # Check if test project already exists
        existing_project = db.query(Project).filter(Project.name == "Report Generation Test").first()
        if existing_project:
            print(f"✓ Test project already exists: {existing_project.id}")
            return str(existing_project.id)
        
        # Create new test project
        test_project = Project(
            name="Report Generation Test",
            description="Test project for report generation exploration scripts",
            created_by="test-user-exploration"  # Test user ID
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)
        
        print(f"✓ Created test project: {test_project.id}")
        return str(test_project.id)
    
    finally:
        db.close()

def verify_services():
    """Verify that all services are properly configured"""
    print("Verifying services configuration...")
    
    # Check database connection
    try:
        db = SessionLocal()
        db.execute(text("SELECT * FROM projects"))
        db.close()
        print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    
    # Check storage service
    try:
        bucket_name = storage_service.bucket_name
        print(f"✓ Storage service configured for bucket: {bucket_name}")
    except Exception as e:
        print(f"✗ Storage service configuration failed: {e}")
        return False
    
    print("✓ All services verified")
    return True

def main():
    """Main setup function"""
    print("=== Report Generation Exploration Setup ===")
    print(f"Environment: {settings.environment}")
    print(f"Database URL: {settings.database_url}")
    print(f"GCS Bucket: {storage_service.bucket_name}")
    print()
    
    # Setup database
    setup_database()
    
    # Verify services
    if not verify_services():
        print("❌ Setup failed - check configuration")
        return
    
    # Setup test project
    project_id = setup_test_project()
    
    print()
    print("=== Setup Complete ===")
    print(f"Test Project ID: {project_id}")
    print("Ready for file upload experiments!")
    print()
    print("Next steps:")
    print("1. Run 01_upload_files.py to test file upload functionality")
    print("2. Run subsequent scripts for parsing and analysis")
    
    return project_id

if __name__ == "__main__":
    main()