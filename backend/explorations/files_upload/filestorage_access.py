import firebase_admin
from firebase_admin import credentials, storage

# --- Initialization ---
# When running locally, the Admin SDK automatically finds the credentials from
# `gcloud auth application-default login`. You don't need a service account key file.
# You just need to specify your Storage Bucket URL.

# Find your bucket URL in the Firebase Console > Storage section.
# It usually looks like 'your-project-id.appspot.com'
STORAGE_BUCKET = 'probtp-poc-prod.firebasestorage.app' 

try:
    firebase_admin.get_app()
except ValueError:
    # Initialize the app with the bucket information
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {
        'storageBucket': STORAGE_BUCKET
    })

# --- Usage Example ---
# Now you can interact with your storage bucket
try:
    print(f"Accessing bucket: {STORAGE_BUCKET}")
    bucket = storage.bucket()
    
    # List all files (blobs) in the root of the bucket
    blobs = bucket.list_blobs()
    
    print("\n--- Files in Bucket ---")
    file_count = 0
    for blob in blobs:
        print(f"- {blob.name}")
        file_count += 1
    
    if file_count == 0:
        print("No files found in the bucket.")

except Exception as e:
    print(f"\nAn error occurred: {e}")
    print("Please ensure your account has the 'Storage Object Viewer' or 'Storage Object Admin' role.")