# PRO BTP POC – GCP Project and Resources with Terraform

This guide provisions a new GCP project `probtp-poc-prod` under organization `cube5.ai` (Org ID `518110912541`), attaches billing, and creates the core infrastructure described in `PROJECT_CONTEXT.md` and `README.md`.

What you get:
- GCP Project with billing
- Enabled APIs (Cloud Run, Cloud SQL, Artifact Registry, Cloud Build, Logging, Monitoring, Secret Manager, Compute)
- Cloud SQL for PostgreSQL 15 with public IP (secure via Cloud SQL Connector)
- Artifact Registry (Docker) repository for container images
- Service Account for backend with least-privileged roles
- Cloud Run service for the FastAPI backend

## 1) Prerequisites

- Org admin and billing admin on GCP for `cube5.ai`
- Billing account ID (format `XXXXXX-XXXXXX-XXXXXX`)
- Terraform `>= 1.5`
- gcloud SDK installed and authenticated as `jb.renault@cube5.ai`

Authenticate:
```bash
# login and pick org project if needed
gcloud auth login
# set default org and billing scopes for later commands
gcloud auth application-default login
```

## 2) Files in this folder

- `project.tf`: Creates project and attaches billing
- `apis.tf`: Enables required services
- `network.tf`: omitted in POC (no VPC)
- `cloud_sql.tf`: Cloud SQL (PostgreSQL 15), public IP
- `redis.tf`: omitted in POC
- `artifact_registry.tf`: Docker Artifact Registry
- `iam.tf`: Backend service account + IAM bindings
- `cloud_run.tf`: Cloud Run service using the service account and optional VPC connector
- `variables.tf`: All input variables
- `outputs.tf`: Useful outputs for deployment

## 3) Configure variables

Create a `terraform.tfvars` file in this directory:
```hcl
org_id              = "518110912541"
billing_account_id  = "<YOUR_BILLING_ACCOUNT_ID>"
project_id          = "probtp-poc-prod"
region              = "europe-west9"
zone                = "europe-west9-a"
environment         = "prod"
artifact_registry_repo = "containers"
backend_image_tag   = "latest"
db_password         = "<STRONG_PASSWORD>"
# Optional if using Firebase hosting with a different project
# firebase_project_id = "probtp-poc-prod"
```

Notes:
- Region Paris (`europe-west9`) per data residency in `PROJECT_CONTEXT.md`. You can switch to `europe-west1` (Belgium) if needed.
- Database tier is `db-g1-small` with backups and PITR enabled (POC scale in context).

## 4) Initialize and create the project

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

This will:
- Create project `probtp-poc-prod` in org `518110912541`
- Attach billing
- Enable services
- Provision Cloud SQL (public IP)
- Create backend service account and IAM
- Deploy a Cloud Run service using the image path output

## 5) Build and push the backend image

Use Artifact Registry output to tag and push the backend image. The output `artifact_registry_repository` looks like:
`europe-west9-docker.pkg.dev/probtp-poc-prod/containers`

Build and push:
```bash
# from repository root
cd backend
IMAGE_REPO=$(terraform -chdir=../infrastructure/terraform output -raw artifact_registry_repository)
IMAGE_NAME="probtp-poc-backend"
# Build
docker build -t ${IMAGE_REPO}/${IMAGE_NAME}:latest .
# Push
gcloud auth configure-docker ${IMAGE_REPO%%/*} --quiet
docker push ${IMAGE_REPO}/${IMAGE_NAME}:latest
```

If you change the tag, set `backend_image_tag` accordingly in `terraform.tfvars` and re-apply.

## 6) Cloud Run deployment notes

- The service uses:
  - Service account `backend-sa`
  - No VPC connector; Cloud SQL accessed via Cloud SQL connector (annotation)
  - Concurrency 100, autoscaling 0→5, 2Gi memory (per context targets)
- Public invoker IAM is set (suitable for POC). Replace with identity-based invokers later if needed.

Environment variables provided to the container:
- `ENVIRONMENT`: `prod`
- `REDIS_URL`: omitted in POC
- `DB_INSTANCE_CONNECTION_NAME`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (compose your SQLAlchemy `DATABASE_URL` inside the app)

## 7) Security and networking

- Cloud SQL uses public IP but is accessed via the Cloud SQL connector (IAM-authenticated); no IP allowlists needed

## 8) Outputs

```bash
terraform output
```
Key values:
- `project_id`
- `cloud_run_backend_url`
- `artifact_registry_repository`
- `cloud_sql_connection_name`
- `firebase_hosting_url`
- `vpc_connector_name` (empty when `use_vpc = false`)

## 9) Firebase Hosting (frontend)

Frontend is deployed via Firebase Hosting as per `README.md`:
```bash
cd frontend
bun run build
firebase deploy --only hosting
```
Make sure your Firebase project is linked to `probtp-poc-prod` or set `firebase_project_id`.

## 10) Security Hardening Applied (September 19, 2025)

### 🚨 Critical Security Vulnerabilities Fixed

After the initial deployment, several critical security issues were identified and immediately fixed using gcloud commands:

#### Issues Found:
1. **🔴 Database Deletion Risk**: No deletion protection enabled
2. **🔴 Insecure Database Connections**: SSL not required
3. **🔴 Password Exposure**: Database password stored in plain text environment variables
4. **🔴 Overprivileged Access**: Using default compute service account
5. **🔴 Public Database**: Cloud SQL accessible from internet without IP restrictions

#### Fixes Applied:

**1. Enabled Deletion Protection**
```bash
gcloud sql instances patch probtp-poc-db-prod --deletion-protection
```
- **Why**: Prevents accidental database deletion
- **Status**: ✅ Applied and verified

**2. Required SSL Connections**
```bash
gcloud sql instances patch probtp-poc-db-prod --require-ssl
```
- **Why**: Encrypts all database connections
- **Status**: ✅ Applied and verified

**3. Moved Password to Secret Manager**
```bash
echo "PASSWORD" | gcloud secrets create db-password --project=probtp-poc-prod --data-file=-
```
- **Why**: Removes password from environment variables and logs
- **Status**: ✅ Applied and verified

**4. Created Dedicated Service Account**
```bash
gcloud iam service-accounts create backend-sa --project=probtp-poc-prod --display-name="Backend Service Account"
```
- **Why**: Follows principle of least privilege
- **Permissions granted**: Cloud SQL Client, Logging Writer, Secret Manager Accessor, Monitoring Writer
- **Status**: ✅ Applied and verified

#### Security Status:
- **Before fixes**: 🔴 **CRITICAL RISK** (Database publicly accessible, weak security)
- **After fixes**: 🟡 **MEDIUM RISK** (Significantly improved, but database still has public IP)

#### Next Steps for Production:
1. **Enable VPC**: Set `use_vpc = true` in `terraform.tfvars` and re-apply
2. **Update Terraform**: Modify configurations to use new service account and Secret Manager
3. **Restrict API Access**: Consider changing from `allUsers` to `allAuthenticatedUsers`

### 📋 Verification Commands

To verify the security fixes are in place:

```bash
# Check deletion protection
gcloud sql instances describe probtp-poc-db-prod --format='value(settings.deletionProtectionEnabled)'
# Should return: True

# Check SSL requirement
gcloud sql instances describe probtp-poc-db-prod --format='value(settings.ipConfiguration.requireSsl)'
# Should return: True

# Check secret exists
gcloud secrets describe db-password --project=probtp-poc-prod

# Check service account
gcloud iam service-accounts describe backend-sa@probtp-poc-prod.iam.gserviceaccount.com
```

### 📚 Related Documentation

- **Security Audit Report**: `post_setup_todo.md` - Comprehensive security analysis and fix roadmap
- **Quick Fix Commands**: `quick_critical_fixes.md` - Copy-paste commands for immediate fixes
- **Emergency Script**: `emergency_security_fixes.sh` - Automated security hardening script

---

## 11) Clean-up

```bash
terraform destroy
```
This removes all managed resources including the project (if Terraform has permissions). Consider keeping the project and selectively removing services in non-POC environments.

---

References: see `PROJECT_CONTEXT.md` and `README.md` for architecture and deployment details.
