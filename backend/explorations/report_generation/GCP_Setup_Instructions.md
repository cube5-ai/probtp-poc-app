# GCP Setup Instructions for Report Generation Exploration

This document provides instructions for setting up the necessary GCP resources for the report generation exploration scripts.

## Prerequisites

- GCP account with billing enabled
- GCP project created (`probtp-poc-prod`)
- `gcloud` CLI installed and configured
- Admin permissions on the GCP project

## Required Services & APIs

### 1. Enable Required APIs

```bash
# Enable Cloud SQL Admin API
gcloud services enable sqladmin.googleapis.com

# Enable Cloud Storage API (should already be enabled)
gcloud services enable storage-component.googleapis.com

# Enable Firebase Storage API
gcloud services enable firebase.googleapis.com
```

## Database Setup

### 1. Cloud SQL Instance Configuration

If not already created, set up a Cloud SQL PostgreSQL instance:

```bash
# Create Cloud SQL instance (if not exists)
gcloud sql instances create probtp-poc-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --storage-type=SSD \
    --storage-size=10GB \
    --backup-start-time=03:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=04 \
    --authorized-networks=0.0.0.0/0
```

### 2. Database and User Setup

```bash
# Set root password (if not set)
gcloud sql users set-password root \
    --instance=probtp-poc-db \
    --password=YOUR_SECURE_PASSWORD

# Create application database
gcloud sql databases create probtp_poc \
    --instance=probtp-poc-db

# Create application user
gcloud sql users create probtp_user \
    --instance=probtp-poc-db \
    --password=YOUR_APP_PASSWORD
```

### 3. Grant Database Permissions

Connect to your Cloud SQL instance and run:

```sql
-- Connect to the database
\c probtp_poc;

-- Grant all privileges to the application user
GRANT ALL PRIVILEGES ON DATABASE probtp_poc TO probtp_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO probtp_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO probtp_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO probtp_user;

-- Allow user to create tables
ALTER USER probtp_user CREATEDB;
```

### 4. Update Connection Settings

Update your backend configuration with the database connection string:

```bash
# Get the connection name
gcloud sql instances describe probtp-poc-db --format="value(connectionName)"
```

Update your `.env` file or environment variables:
```env
DATABASE_URL=postgresql://probtp_user:YOUR_APP_PASSWORD@/probtp_poc?host=/cloudsql/YOUR_PROJECT_ID:us-central1:probtp-poc-db
```

For local development (with Cloud SQL Proxy):
```env
DATABASE_URL=postgresql://probtp_user:YOUR_APP_PASSWORD@localhost:5432/probtp_poc
```

## Storage Setup

### 1. Firebase Storage Bucket

The bucket should already be configured. Verify access:

```bash
# List buckets
gsutil ls

# Check bucket permissions
gsutil iam get gs://probtp-poc-prod.firebasestorage.app
```

### 2. Service Account Setup

Create a service account for the application (if not exists):

```bash
# Create service account
gcloud iam service-accounts create probtp-backend-sa \
    --display-name="ProBTP Backend Service Account" \
    --description="Service account for ProBTP backend application"

# Grant necessary roles
gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:probtp-backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:probtp-backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Create and download key
gcloud iam service-accounts keys create backend-sa-key.json \
    --iam-account=probtp-backend-sa@probtp-poc-prod.iam.gserviceaccount.com
```

## Schema Setup for Exploration

### 1. Initialize Database Schema

The exploration scripts will automatically create the necessary tables when you run the setup script:

```bash
cd backend/explorations/report_generation
python 00_config_and_setup.py
```

This script will:
- Create all necessary database tables (`projects`, `files`, `project_members`)
- Verify service connections
- Create a test project for experimentation

### 2. Verify Schema Creation

Connect to your database and verify the schema:

```sql
-- List all tables
\dt

-- Check projects table
\d projects

-- Check files table  
\d files

-- Check project_members table
\d project_members
```

Expected tables:
- `projects` - Project management
- `files` - File metadata and storage references
- `project_members` - User-project associations

## Environment Configuration

### 1. Set Environment Variables

```bash
export ENVIRONMENT=development
export DATABASE_URL="your-database-url"
export GCS_PROJECT_ID=probtp-poc-prod
export GCS_BUCKET_NAME=probtp-poc-prod
export FIREBASE_PROJECT_ID=probtp-poc-prod
export GOOGLE_APPLICATION_CREDENTIALS=./backend-sa-key.json
```

### 2. Test Configuration

Run the setup script to verify everything is working:

```bash
cd backend/explorations/report_generation
python 00_config_and_setup.py
```

Expected output:
```
=== Report Generation Exploration Setup ===
Environment: development
Database URL: postgresql://...
GCS Bucket: probtp-poc-prod

Setting up database tables...
✓ Database tables created/verified
Verifying services configuration...
✓ Database connection successful
✓ Storage service configured for bucket: probtp-poc-prod
✓ All services verified
✓ Test project already exists: 12345678-1234-5678-9012-123456789012

=== Setup Complete ===
Test Project ID: 12345678-1234-5678-9012-123456789012
Ready for file upload experiments!
```

## Troubleshooting

### Database Connection Issues

1. **Cloud SQL Proxy** (for local development):
```bash
# Download and run Cloud SQL Proxy
./cloud_sql_proxy -instances=probtp-poc-prod:us-central1:probtp-poc-db=tcp:5432
```

2. **Check authorized networks**:
```bash
gcloud sql instances describe probtp-poc-db --format="value(settings.ipConfiguration.authorizedNetworks)"
```

### Storage Permission Issues

1. **Check service account roles**:
```bash
gcloud projects get-iam-policy probtp-poc-prod \
    --filter="bindings.members:serviceAccount:probtp-backend-sa@probtp-poc-prod.iam.gserviceaccount.com"
```

2. **Test storage access**:
```bash
gsutil ls gs://probtp-poc-prod.firebasestorage.app
```

### Application Credential Issues

1. **Verify service account key**:
```bash
gcloud auth activate-service-account --key-file=backend-sa-key.json
gcloud auth list
```

2. **Test application default credentials**:
```bash
gcloud auth application-default login
```

## Security Notes

- Keep service account keys secure and never commit them to version control
- Use least privilege principle for service account roles
- Consider using Workload Identity for production deployments
- Enable audit logging for sensitive operations
- Regularly rotate service account keys

## Next Steps

After completing this setup:

1. Run `00_config_and_setup.py` to initialize the database schema
2. Run `01_upload_files.py` to test file upload functionality
3. Proceed with the report generation exploration scripts
4. Monitor costs and resource usage in the GCP Console

For any issues, check the GCP Console logs and ensure all APIs are enabled and permissions are correctly configured.
