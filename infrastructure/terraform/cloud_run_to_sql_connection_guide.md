# Cloud Run to Cloud SQL Connection Guide

## Overview

This guide explains how your FastAPI backend (running on Cloud Run) connects securely to your PostgreSQL database (Cloud SQL) in the ProBTP POC infrastructure.

## Connection Architecture

```
┌─────────────────┐    Cloud SQL Connector    ┌──────────────────┐
│   Cloud Run     │◄──────────────────────────►│   Cloud SQL      │
│   (FastAPI)     │    (IAM Authentication)    │   (PostgreSQL)   │
└─────────────────┘                            └──────────────────┘
```

## How the Connection Works

### 1. Cloud SQL Connector Annotation

In your `cloud_run.tf`, the connection is established using the Cloud SQL connector annotation:

```hcl
# cloud_run.tf
metadata {
  annotations = {
    "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.main.connection_name
  }
}
```

**What this does:**
- Automatically installs the Cloud SQL Auth Proxy as a sidecar container
- Creates a Unix socket connection to your database
- Handles IAM authentication automatically

### 2. Environment Variables

Your Cloud Run service receives these environment variables for database connection:

```hcl
# cloud_run.tf - Environment variables passed to your FastAPI app
env {
  name  = "DB_INSTANCE_CONNECTION_NAME"
  value = google_sql_database_instance.main.connection_name
  # Example: "probtp-poc-prod:europe-west9:probtp-poc-db-prod"
}

env {
  name  = "DB_NAME"
  value = google_sql_database.main.name
  # Example: "probtp_poc_prod"
}

env {
  name  = "DB_USER"
  value = google_sql_user.backend.name
  # Example: "probtp_poc_user"
}

env {
  name  = "DB_PASSWORD"
  value = var.db_password  # ⚠️ Now moved to Secret Manager for security
}
```

### 3. IAM Authentication

Your Cloud Run service uses a service account with the required permissions:

```hcl
# iam.tf - Service account permissions
resource "google_project_iam_member" "backend_cloudsql_client" {
  project = google_project.project.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:backend-sa@probtp-poc-prod.iam.gserviceaccount.com"
}
```

**What this permission allows:**
- Connect to Cloud SQL instances
- Use the Cloud SQL Auth Proxy
- Authenticate using IAM (no need for IP allowlisting)

## Connection Methods

### Current Setup: Public IP with Cloud SQL Connector

```
Cloud Run → Cloud SQL Auth Proxy → Internet → Cloud SQL (Public IP)
```

**Characteristics:**
- ✅ Simple setup, no VPC required
- ✅ Secure (IAM authenticated, SSL encrypted)
- ✅ No IP allowlisting needed
- ⚠️ Traffic goes over public internet (encrypted)

### Future Setup: Private IP with VPC (Recommended for Production)

When you set `use_vpc = true`:

```
Cloud Run → VPC Connector → Private VPC → Cloud SQL (Private IP)
```

**Characteristics:**
- ✅ Traffic stays within Google's private network
- ✅ Better security and performance
- ✅ Network isolation
- ❌ More complex setup

## FastAPI Database Connection Code

Your FastAPI application should connect using these patterns:

### Option 1: Using Cloud SQL Connector (Current)

```python
# In your FastAPI app
import os
import sqlalchemy

# Get connection details from environment
connection_name = os.getenv("DB_INSTANCE_CONNECTION_NAME")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")  # Move to Secret Manager

# Create database URL for Cloud SQL Connector
DATABASE_URL = f"postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host=/cloudsql/{connection_name}"

# Create engine
engine = sqlalchemy.create_engine(DATABASE_URL)
```

### Option 2: Using Secret Manager (Recommended)

```python
# In your FastAPI app
import os
from google.cloud import secretmanager

def get_db_password():
    """Retrieve database password from Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    project_id = "probtp-poc-prod"
    secret_name = "db-password"
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get connection details
connection_name = os.getenv("DB_INSTANCE_CONNECTION_NAME")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = get_db_password()  # From Secret Manager

# Create database URL
DATABASE_URL = f"postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host=/cloudsql/{connection_name}"
```

## Security Features

### Current Security Measures

1. **SSL Encryption**: All connections require SSL (`--require-ssl` applied)
2. **IAM Authentication**: No need for IP allowlisting
3. **Service Account**: Dedicated `backend-sa` with minimal permissions
4. **Deletion Protection**: Database cannot be accidentally deleted
5. **Secret Manager**: Database password stored securely (recommended)

### Connection Security Flow

```
1. Cloud Run starts with service account credentials
2. Cloud SQL Auth Proxy validates IAM permissions
3. SSL connection established to Cloud SQL
4. Database authenticates using username/password
5. Encrypted data transfer over SSL
```

## Troubleshooting Connection Issues

### Common Issues and Solutions

**1. Connection Refused**
```bash
# Check if Cloud SQL instance is running
gcloud sql instances describe probtp-poc-db-prod

# Check service account permissions
gcloud projects get-iam-policy probtp-poc-prod --flatten="bindings[].members" --filter="bindings.members:backend-sa"
```

**2. Authentication Failed**
```bash
# Verify database user exists
gcloud sql users list --instance=probtp-poc-db-prod

# Check if SSL is required
gcloud sql instances describe probtp-poc-db-prod --format='value(settings.ipConfiguration.requireSsl)'
```

**3. Environment Variables Missing**
```bash
# Check Cloud Run environment variables
gcloud run services describe probtp-poc-backend-prod --region=europe-west9 --format="export"
```

## Testing the Connection

### From Cloud Run Container

```bash
# If you need to debug from within the container
# The Cloud SQL socket is available at:
/cloudsql/probtp-poc-prod:europe-west9:probtp-poc-db-prod

# Test with psql (if installed in container)
psql "host=/cloudsql/probtp-poc-prod:europe-west9:probtp-poc-db-prod dbname=probtp_poc_prod user=probtp_poc_user"
```

### From Local Development

```bash
# Use Cloud SQL Auth Proxy for local development
cloud_sql_proxy -instances=probtp-poc-prod:europe-west9:probtp-poc-db-prod=tcp:5432 &

# Connect locally
psql "host=127.0.0.1 port=5432 dbname=probtp_poc_prod user=probtp_poc_user"
```

## Next Steps

### To Improve Security (Recommended)

1. **Enable VPC**: Set `use_vpc = true` in `terraform.tfvars`
2. **Update to Secret Manager**: Modify Cloud Run to use Secret Manager for DB password
3. **Enable IAM Database Authentication**: Use IAM for database user authentication (advanced)

### To Monitor Connections

1. **Enable Query Insights**: Monitor database performance
2. **Set up Alerts**: Alert on connection failures or high latency
3. **Log Analysis**: Review Cloud Run and Cloud SQL logs

---

**Key Takeaway**: Your current setup uses the Cloud SQL Connector for secure, IAM-authenticated connections over the public internet. For production, consider enabling VPC for private network connectivity.
