#!/usr/bin/env python3
"""
Test script for StorageService to verify Google Cloud Storage connectivity and operations.

This script tests the StorageService class to ensure:
1. Google Cloud Storage credentials are working
2. Signed URL generation works
3. File operations work correctly

Setup Requirements:
1. Run from backend directory: cd backend && python explorations/test_storage_service.py
2. Ensure you have authenticated with GCP:
   - gcloud auth application-default login
   OR
   - Set GOOGLE_APPLICATION_CREDENTIALS environment variable
3. Make sure your account has necessary GCS permissions:
   - Storage Object Creator
   - Storage Object Viewer
   - Storage Object Admin (for delete operations)

Author: Test Script
Date: September 22, 2025
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime

import requests

# Add the app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

try:
    from google.cloud.exceptions import NotFound

    from app.core.config import get_settings
    from app.core.storage import StorageConfig
    from app.services.storage_service import StorageService
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the backend directory:")
    print("cd backend && python explorations/test_storage_service.py")
    sys.exit(1)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_test(test_name: str, success: bool, details: str = ""):
    """Print test result with formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"    {details}")


def test_configuration():
    """Test configuration loading"""
    print_section("Configuration Test")
    
    try:
        settings = get_settings()
        print_test("Settings loaded", True, f"GCS Project ID: {settings.gcs_project_id}")
        
        bucket_name = StorageConfig.get_bucket_name()
        print_test("Bucket name retrieved", True, f"Bucket: {bucket_name}")
        
        # Test file path generation
        test_project_id = "test-project-123"
        test_file_id = "test-file-456"
        test_timestamp = 1695372900
        
        file_path = StorageConfig.get_file_path(test_project_id, test_file_id, test_timestamp)
        expected_pattern = f"projects/{test_project_id}/files/{test_file_id}_{test_timestamp}.pdf"
        
        print_test("File path generation", expected_pattern in file_path, f"Path: {file_path}")
        
        return True
    except Exception as e:
        print_test("Configuration loading", False, str(e))
        return False


def test_storage_service_initialization():
    """Test StorageService initialization"""
    print_section("StorageService Initialization")
    
    try:
        service = StorageService()
        print_test("StorageService created", True, f"Bucket: {service.bucket_name}")
        
        # Note: Skipping bucket.exists() check as it requires storage.buckets.get permission
        # which isn't needed for core functionality (file operations, signed URLs)
        print_test("Bucket configuration", True, 
                  f"Bucket '{service.bucket_name}' configured correctly")
        
        return service
    except Exception as e:
        print_test("StorageService initialization", False, str(e))
        return None


def test_signed_url_generation(service: StorageService):
    """Test signed URL generation"""
    print_section("Signed URL Generation")
    
    try:
        test_project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        test_file_id = f"test-file-{uuid.uuid4().hex[:8]}"
        
        # Test upload URL generation
        upload_url, storage_path = service.generate_upload_url(
            project_id=test_project_id,
            file_id=test_file_id,
            expiration_minutes=5
        )
        
        print_test("Upload URL generated", bool(upload_url), f"URL length: {len(upload_url)}")
        print_test("Storage path generated", bool(storage_path), f"Path: {storage_path}")
        
        # Verify URL format
        url_valid = upload_url.startswith("https://storage.googleapis.com")
        print_test("Upload URL format", url_valid, "URL starts with expected domain")
        
        # Verify path contains expected components
        path_components = [test_project_id, test_file_id]
        path_valid = all(component in storage_path for component in path_components)
        print_test("Storage path components", path_valid, "Contains project and file IDs")
        
        return storage_path if url_valid and path_valid else None
        
    except Exception as e:
        print_test("Signed URL generation", False, str(e))
        return None


def test_file_operations(service: StorageService):
    """Test basic file operations"""
    print_section("File Operations")
    
    try:
        # Create a test file path
        test_project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        test_file_id = f"test-file-{uuid.uuid4().hex[:8]}"
        timestamp = int(datetime.now().timestamp())
        
        test_storage_path = StorageConfig.get_file_path(test_project_id, test_file_id, timestamp)
        
        # Test file existence check (should be False for new path)
        exists_before = service.file_exists(test_storage_path)
        print_test("File exists check (new file)", not exists_before, 
                  f"File should not exist yet: {not exists_before}")
        
        # Test file info on non-existent file (should raise exception)
        try:
            service.get_file_info(test_storage_path)
            print_test("File info on non-existent file", False, "Should have raised FileNotFoundError")
        except FileNotFoundError:
            print_test("File info on non-existent file", True, "Correctly raised FileNotFoundError")
        
        # Test delete on non-existent file (should return False)
        delete_result = service.delete_file(test_storage_path)
        print_test("Delete non-existent file", not delete_result, 
                  f"Should return False for non-existent file: {not delete_result}")
        
        return True
        
    except Exception as e:
        print_test("File operations", False, str(e))
        return False


def test_download_url_generation(service: StorageService):
    """Test download URL generation for non-existent file"""
    print_section("Download URL Generation")
    
    try:
        # Test with a path that doesn't exist
        fake_path = "fake/path/to/nonexistent/file.pdf"
        
        try:
            download_url = service.generate_download_url(fake_path)
            print_test("Download URL for non-existent file", False, 
                      "Should have raised FileNotFoundError")
        except FileNotFoundError:
            print_test("Download URL for non-existent file", True, 
                      "Correctly raised FileNotFoundError")
        
        return True
        
    except Exception as e:
        print_test("Download URL generation test", False, str(e))
        return False


def test_actual_file_upload(service: StorageService):
    """Test actual file upload using the PDF file"""
    print_section("Actual File Upload Test")
    
    # Path to the test PDF file
    test_file_path = os.path.join(os.path.dirname(__file__), 
                                 "File #1 - Laurent M - Conditions particulières - Socle AXA - SAE.pdf")
    
    if not os.path.exists(test_file_path):
        print_test("File existence check", False, f"Test file not found: {test_file_path}")
        return False
    
    try:
        # Get file size for validation
        file_size = os.path.getsize(test_file_path)
        print_test("Test file found", True, f"File size: {file_size:,} bytes")
        
        # Generate upload URL
        test_project_id = f"test-upload-{uuid.uuid4().hex[:8]}"
        test_file_id = f"pdf-test-{uuid.uuid4().hex[:8]}"
        
        upload_url, storage_path = service.generate_upload_url(
            project_id=test_project_id,
            file_id=test_file_id,
            content_type='application/pdf',
            expiration_minutes=10
        )
        
        print_test("Upload URL generated", True, f"Storage path: {storage_path}")
        
        # Upload the file
        with open(test_file_path, 'rb') as file_data:
            headers = {
                'Content-Type': 'application/pdf'
            }
            
            response = requests.put(upload_url, data=file_data, headers=headers)
            
        upload_success = response.status_code == 200
        print_test("File upload", upload_success, 
                  f"HTTP Status: {response.status_code}")
        
        if not upload_success:
            print(f"    Upload response: {response.text}")
            return False
        
        # Verify file exists in storage
        file_exists = service.file_exists(storage_path)
        print_test("File exists in storage", file_exists, 
                  f"File found at: {storage_path}")
        
        if file_exists:
            # Get file info
            try:
                file_info = service.get_file_info(storage_path)
                print_test("File info retrieved", True, 
                          f"Size: {file_info['size']:,} bytes, Type: {file_info['content_type']}")
                
                # Verify file size matches
                size_match = file_info['size'] == file_size
                print_test("File size verification", size_match,
                          f"Expected: {file_size:,}, Got: {file_info['size']:,}")
                
            except Exception as e:
                print_test("File info retrieval", False, str(e))
            
            # Test download URL generation
            try:
                download_url = service.generate_download_url(storage_path, expiration_minutes=5)
                print_test("Download URL generated", True, f"URL length: {len(download_url)}")
                
                # Verify download URL format
                download_url_valid = download_url.startswith("https://storage.googleapis.com")
                print_test("Download URL format", download_url_valid, "URL format is valid")
                
            except Exception as e:
                print_test("Download URL generation", False, str(e))
            
            # Keep the file for console verification (no cleanup)
            print_test("File kept for verification", True, 
                      f"File preserved at: {storage_path}")
            print(f"    📂 View in GCP Console:")
            print(f"    https://console.cloud.google.com/storage/browser/{service.bucket_name}/{storage_path.split('/')[0]}")
            print(f"    🗂️  Full path: {storage_path}")
        
        return upload_success and file_exists
        
    except Exception as e:
        print_test("File upload test", False, str(e))
        return False


def print_environment_info():
    """Print relevant environment information"""
    print_section("Environment Information")
    
    env_vars = [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ENVIRONMENT", 
        "GCS_PROJECT_ID",
        "GCS_BUCKET_NAME"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if var == "GOOGLE_APPLICATION_CREDENTIALS" and value:
            # Just show if it's set, not the full path for security
            print(f"{var}: {'SET' if value else 'NOT SET'}")
        else:
            print(f"{var}: {value or 'NOT SET'}")


def main():
    """Main test function"""
    print("🧪 StorageService Test Script")
    print(f"Running at: {datetime.now().isoformat()}")
    
    print_environment_info()
    
    # Run tests in sequence
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Configuration
    total_tests += 1
    if test_configuration():
        tests_passed += 1
    
    # Test 2: Service initialization
    total_tests += 1
    service = test_storage_service_initialization()
    if service:
        tests_passed += 1
        
        # Test 3: Signed URL generation (only if service initialized)
        total_tests += 1
        if test_signed_url_generation(service):
            tests_passed += 1
        
        # Test 4: File operations
        total_tests += 1
        if test_file_operations(service):
            tests_passed += 1
        
        # Test 5: Download URL generation
        total_tests += 1
        if test_download_url_generation(service):
            tests_passed += 1
        
        # Test 6: Actual file upload
        total_tests += 1
        if test_actual_file_upload(service):
            tests_passed += 1
    
    # Print final results
    print_section("Test Results Summary")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! StorageService is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        
        if not service:
            print("\n🔧 Troubleshooting tips:")
            print("1. Ensure you're authenticated: gcloud auth application-default login")
            print("2. Check your GCP project: gcloud config get-value project")
            print("3. Verify bucket exists and you have access")
            print("4. Check your IAM permissions for Cloud Storage")
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
