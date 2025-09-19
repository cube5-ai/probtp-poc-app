# 🚨 IMMEDIATE CRITICAL SECURITY FIXES

## Execute These Commands RIGHT NOW

Copy and paste these commands one by one to fix the most critical security vulnerabilities:

### Set your project context
```bash
gcloud config set project probtp-poc-prod
```

### 1. 🔴 Enable deletion protection (prevents accidental DB deletion)
```bash
gcloud sql instances patch probtp-poc-db-prod \
    --deletion-protection
```

### 2. 🔴 Require SSL for all database connections
```bash
gcloud sql instances patch probtp-poc-db-prod \
    --require-ssl
```

### 3. 🔴 Move database password to Secret Manager
```bash
echo "X0i7!W0e3/CIgg" | gcloud secrets create db-password \
    --project=probtp-poc-prod \
    --data-file=-
```

### 4. 🔴 Create dedicated backend service account
```bash
gcloud iam service-accounts create backend-sa \
    --project=probtp-poc-prod \
    --display-name="Backend Service Account" \
    --description="Dedicated service account for FastAPI backend"
```

### 5. 🔴 Grant minimal required permissions
```bash
# Cloud SQL access
gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Logging
gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"

# Secret Manager
gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Monitoring
gcloud projects add-iam-policy-binding probtp-poc-prod \
    --member="serviceAccount:backend-sa@probtp-poc-prod.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"
```

## ✅ Verification Commands

After running the fixes above, verify they worked:

```bash
# Check deletion protection is enabled
gcloud sql instances describe probtp-poc-db-prod \
    --format='value(settings.deletionProtectionEnabled)'
# Should return: True

# Check SSL is required
gcloud sql instances describe probtp-poc-db-prod \
    --format='value(settings.ipConfiguration.requireSsl)'
# Should return: True

# Check secret exists
gcloud secrets describe db-password --project=probtp-poc-prod
# Should show secret details

# Check service account exists
gcloud iam service-accounts describe backend-sa@probtp-poc-prod.iam.gserviceaccount.com
# Should show service account details
```

## 🔄 Next Step: Enable VPC (Critical but requires Terraform)

**The database is STILL publicly accessible!** To fully secure it:

1. Edit `terraform.tfvars`:
   ```
   use_vpc = true
   ```

2. Apply the change:
   ```bash
   cd /Users/jb/Documents/Work/Pro/Cube5/probtp-poc-app/infrastructure/terraform
   terraform plan
   terraform apply
   ```

This will create a VPC and move your database to a private IP, fully securing it.

## 🟡 Optional: Restrict Cloud Run Access

**WARNING**: This will break public API access. Only run if you have authentication ready:

```bash
# Remove public access
gcloud run services remove-iam-policy-binding probtp-poc-backend-prod \
    --region=europe-west9 \
    --member='allUsers' \
    --role='roles/run.invoker'

# Add authenticated users only
gcloud run services add-iam-policy-binding probtp-poc-backend-prod \
    --region=europe-west9 \
    --member='allAuthenticatedUsers' \
    --role='roles/run.invoker'
```

---

**Time to complete**: 5-10 minutes  
**Risk reduction**: HIGH → MEDIUM  
**Next**: Enable VPC to achieve LOW risk
