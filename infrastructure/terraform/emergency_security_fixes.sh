#!/bin/bash
# Emergency Security Fixes for ProBTP POC Infrastructure
# Run these commands to immediately secure your critical vulnerabilities

set -e  # Exit on any error

# Configuration
PROJECT_ID="probtp-poc-prod"
REGION="europe-west9"
DB_INSTANCE_NAME="probtp-poc-db-prod"
CLOUD_RUN_SERVICE="probtp-poc-backend-prod"

echo "🚨 EMERGENCY SECURITY FIXES FOR PROJECT: $PROJECT_ID"
echo "============================================================"

# Set the active project
echo "1. Setting active GCP project..."
gcloud config set project $PROJECT_ID

echo ""
echo "🔴 CRITICAL FIX 1: Enable deletion protection on Cloud SQL"
echo "-----------------------------------------------------------"
gcloud sql instances patch $DB_INSTANCE_NAME \
    --deletion-protection
echo "✅ Deletion protection enabled"

echo ""
echo "🔴 CRITICAL FIX 2: Require SSL connections to database"
echo "------------------------------------------------------"
gcloud sql instances patch $DB_INSTANCE_NAME \
    --require-ssl
echo "✅ SSL requirement enabled"

echo ""
echo "🔴 CRITICAL FIX 3: Create Secret Manager secret for DB password"
echo "---------------------------------------------------------------"
# Check if secret already exists
if gcloud secrets describe db-password --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "⚠️  Secret 'db-password' already exists, skipping creation"
else
    echo "X0i7!W0e3/CIgg" | gcloud secrets create db-password \
        --project=$PROJECT_ID \
        --data-file=-
    echo "✅ Database password moved to Secret Manager"
fi

echo ""
echo "🔴 CRITICAL FIX 4: Create dedicated backend service account"
echo "----------------------------------------------------------"
# Check if service account already exists
if gcloud iam service-accounts describe backend-sa@$PROJECT_ID.iam.gserviceaccount.com --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "⚠️  Service account 'backend-sa' already exists, skipping creation"
else
    gcloud iam service-accounts create backend-sa \
        --project=$PROJECT_ID \
        --display-name="Backend Service Account" \
        --description="Dedicated service account for FastAPI backend"
    echo "✅ Backend service account created"
fi

echo ""
echo "🔴 CRITICAL FIX 5: Grant minimal required permissions to backend SA"
echo "-------------------------------------------------------------------"
# Cloud SQL Client
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:backend-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Logging
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:backend-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"

# Secret Manager Access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:backend-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Monitoring
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:backend-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"

echo "✅ Minimal permissions granted to backend service account"

echo ""
echo "🟡 OPTIONAL FIX 6: Restrict Cloud Run access to authenticated users"
echo "-------------------------------------------------------------------"
echo "⚠️  This will break public access - only run if you have authentication ready"
echo "To apply this fix, run:"
echo "gcloud run services remove-iam-policy-binding $CLOUD_RUN_SERVICE \\"
echo "    --region=$REGION \\"
echo "    --member='allUsers' \\"
echo "    --role='roles/run.invoker'"
echo ""
echo "gcloud run services add-iam-policy-binding $CLOUD_RUN_SERVICE \\"
echo "    --region=$REGION \\"
echo "    --member='allAuthenticatedUsers' \\"
echo "    --role='roles/run.invoker'"

echo ""
echo "🟡 NEXT STEP: Update your Terraform configuration"
echo "-------------------------------------------------"
echo "1. Edit terraform.tfvars and set: use_vpc = true"
echo "2. Run: terraform plan"
echo "3. Run: terraform apply"
echo "   This will create VPC and move database to private IP"

echo ""
echo "🧪 VERIFICATION COMMANDS"
echo "========================"
echo "# Check deletion protection:"
echo "gcloud sql instances describe $DB_INSTANCE_NAME --format='value(settings.deletionProtectionEnabled)'"
echo ""
echo "# Check SSL requirement:"
echo "gcloud sql instances describe $DB_INSTANCE_NAME --format='value(settings.ipConfiguration.requireSsl)'"
echo ""
echo "# Check secret exists:"
echo "gcloud secrets describe db-password"
echo ""
echo "# Check service account:"
echo "gcloud iam service-accounts describe backend-sa@$PROJECT_ID.iam.gserviceaccount.com"

echo ""
echo "✅ CRITICAL SECURITY FIXES COMPLETED!"
echo "======================================"
echo "Your database now has:"
echo "- ✅ Deletion protection enabled"
echo "- ✅ SSL connections required"
echo "- ✅ Password stored in Secret Manager"
echo "- ✅ Dedicated service account with minimal permissions"
echo ""
echo "🚨 IMPORTANT: Your database still has a public IP!"
echo "To fully secure it, enable VPC by setting use_vpc=true in terraform.tfvars"
echo "and running terraform apply."
