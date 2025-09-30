"""
File upload script for report generation exploration
- Upload test files using the storage service
- Create file records in database
- Generate signed URLs for upload/download


Run the following command to access the Cloud SQL:
Local to Cloud SQL
Use the Cloud SQL Auth Proxy:
- cloud-sql-proxy --port 5433 probtp-poc-prod:europe-west9:probtp-poc-db-prod
- Set DATABASE_URL=postgresql://<user>:<pass>@127.0.0.1:5433/<db>
Or connect to a public IP (if enabled and allowed) by pointing DATABASE_URL at the public host.
"""
import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend app to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, backend_path)

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.file import File
from app.models.project import Project
from app.services.storage_service import StorageService

# Initialize services
settings = get_settings()
storage_service = StorageService()

def get_test_project_id():
    """Get the test project ID created by setup script"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == "Report Generation Test").first()
        if not project:
            print("❌ Test project not found. Please run 00_config_and_setup.py first.")
            return None
        return str(project.id)
    finally:
        db.close()

def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def create_file_record(project_id: str, file_path: str, uploaded_by: str = "test-user-exploration") -> File:
    """Create a file record in the database"""
    db = SessionLocal()
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = calculate_file_hash(file_path)
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Generate signed upload URL
        upload_url, storage_path = storage_service.generate_upload_url(
            project_id=project_id,
            file_id=file_id,
            content_type='application/pdf'
        )
        
        # Create file record
        file_record = File(
            id=file_id,
            project_id=project_id,
            original_name=file_name,
            storage_path=storage_path,
            file_size=file_size,
            mime_type='application/pdf',
            md5_hash=file_hash,
            status='pending',
            upload_url=upload_url,
            upload_url_expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.upload_url_expiration_minutes),
            uploaded_by=uploaded_by
        )
        
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
        print(f"✓ Created file record: {file_record.id}")
        print(f"  Name: {file_record.original_name}")
        print(f"  Size: {file_record.file_size} bytes")
        print(f"  Storage path: {file_record.storage_path}")
        
        return file_record
    
    finally:
        db.close()

def upload_file_to_storage(file_record: File, local_file_path: str) -> bool:
    """Upload file to cloud storage using signed URL"""
    try:
        import requests
        
        print(f"Uploading {file_record.original_name} to cloud storage...")
        
        # Read file content
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload using signed URL
        response = requests.put(
            file_record.upload_url,
            data=file_content,
            headers={'Content-Type': file_record.mime_type}
        )
        
        if response.status_code == 200:
            print(f"✓ Upload successful for {file_record.original_name}")
            
            # Update file status to ready
            db = SessionLocal()
            try:
                db_file = db.query(File).filter(File.id == file_record.id).first()
                if db_file:
                    db_file.mark_as_ready()
                    db.commit()
                    print(f"✓ File status updated to 'ready'")
            finally:
                db.close()
            
            return True
        else:
            print(f"❌ Upload failed for {file_record.original_name}: {response.status_code}")
            
            # Mark file as failed
            db = SessionLocal()
            try:
                db_file = db.query(File).filter(File.id == file_record.id).first()
                if db_file:
                    db_file.mark_as_failed(f"Upload failed with status {response.status_code}")
                    db.commit()
            finally:
                db.close()
            
            return False
    
    except Exception as e:
        print(f"❌ Upload error for {file_record.original_name}: {e}")
        
        # Mark file as failed
        db = SessionLocal()
        try:
            db_file = db.query(File).filter(File.id == file_record.id).first()
            if db_file:
                db_file.mark_as_failed(str(e))
                db.commit()
        finally:
            db.close()
        
        return False

def test_download_url(file_record: File):
    """Test generating and accessing download URL"""
    try:
        download_url = storage_service.generate_download_url(file_record.storage_path)
        print(f"✓ Generated download URL for {file_record.original_name}")
        print(f"  URL expires in {settings.download_url_expiration_minutes} minutes")
        
        # Test if file exists in storage
        exists = storage_service.file_exists(file_record.storage_path)
        print(f"✓ File exists in storage: {exists}")
        
        if exists:
            # Get file info
            file_info = storage_service.get_file_info(file_record.storage_path)
            print(f"✓ File info:")
            print(f"  Size: {file_info['size']} bytes")
            print(f"  Content Type: {file_info['content_type']}")
            print(f"  Created: {file_info['created']}")
        
        return download_url
    
    except Exception as e:
        print(f"❌ Error generating download URL: {e}")
        return None

def find_test_files():
    """Find test PDF files in the files_upload directory"""
    documents_dir = os.path.join(os.path.dirname(__file__), 'documents')
    pdf_files = []
    
    if os.path.exists(documents_dir):
        for file in os.listdir(documents_dir):
            if file.endswith('.pdf'):
                pdf_files.append(os.path.join(documents_dir, file))
    
    return pdf_files

def main():
    """Main upload function"""
    print("=== File Upload Test ===")
    
    # Get test project
    project_id = get_test_project_id()
    if not project_id:
        return
    
    print(f"Using test project: {project_id}")
    
    # Find test files
    test_files = find_test_files()
    
    if not test_files:
        print("❌ No PDF files found in ../files_upload/ directory")
        print("Please add some test PDF files to upload")
        return
    
    print(f"Found {len(test_files)} test files:")
    for file_path in test_files:
        print(f"  - {os.path.basename(file_path)}")
    
    print()
    
    # Process each file
    uploaded_files = []
    for file_path in test_files:
        print(f"Processing: {os.path.basename(file_path)}")
        
        # Create file record
        file_record = create_file_record(project_id, file_path)
        
        # Upload to storage
        if upload_file_to_storage(file_record, file_path):
            uploaded_files.append(file_record)
            
            # Test download URL
            download_url = test_download_url(file_record)
            if download_url:
                print(f"✓ Download URL: {download_url[:100]}...")
        
        print("-" * 50)
    
    # Summary
    print()
    print("=== Upload Summary ===")
    print(f"Total files processed: {len(test_files)}")
    print(f"Successfully uploaded: {len(uploaded_files)}")
    
    if uploaded_files:
        print()
        print("Successfully uploaded files:")
        for file_record in uploaded_files:
            print(f"  - {file_record.original_name} (ID: {file_record.id})")
        
        print()
        print("Next steps:")
        print("1. Run 02_read_and_parse_file.py to test file parsing")
        print("2. Check files in Firebase Storage console")
        print("3. Verify file records in database")

if __name__ == "__main__":
    main()
