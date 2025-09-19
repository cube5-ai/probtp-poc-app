# Security Audit & Hardening - Infrastructure Review

## 🔴 CRITICAL SECURITY FINDINGS

Your Terraform infrastructure has several security vulnerabilities that need attention before production deployment.

## Issue 1: Cloud Run Public Access 🔴 HIGH RISK

### Current Configuration
```hcl
# In cloud_run.tf
resource "google_cloud_run_service_iam_member" "public" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"  # ← This allows ANYONE to access your API
}
```

## Issue 2: Cloud SQL Public IP + No Network Restrictions 🔴 HIGH RISK

### Current Configuration
```hcl
# In cloud_sql.tf
resource "google_sql_database_instance" "main" {
  settings {
    ip_configuration {
      ipv4_enabled = true  # ← Public IP with NO authorized networks
      # No authorized_networks block = accessible from ANY IP
    }
  }
  deletion_protection = false  # ← Database can be accidentally deleted
}
```

**Risk**: Your PostgreSQL database is accessible from the internet without IP restrictions!

## Issue 3: Database Password in Plain Text 🟡 MEDIUM RISK

### Current Configuration
```hcl
# In cloud_run.tf
env {
  name  = "DB_PASSWORD"
  value = var.db_password  # ← Plain text in environment variables
}
```

**Risk**: Database password visible in Cloud Run console and logs.

## Issue 4: Overprivileged Service Account 🟡 MEDIUM RISK

### Current Configuration
```hcl
# In iam.tf - Using default compute service account
service_account_name = "${google_project.project.number}-compute@developer.gserviceaccount.com"
```

**Risk**: Using default service account instead of least-privilege custom account.

## Issue 5: Missing Security Features 🟡 MEDIUM RISK

- ❌ No VPC network isolation
- ❌ No Cloud Armor (DDoS protection)
- ❌ No audit logging enabled
- ❌ No SSL certificate management
- ❌ No backup encryption keys specified
- ❌ No network access logging

## Security Risk Assessment

### POC Phase (Current - ⚠️ RISKY BUT MANAGEABLE)
- ✅ Easy testing and development
- ✅ No complex networking setup
- 🔴 Database publicly accessible
- 🔴 API publicly accessible
- 🟡 Passwords in environment variables
- 🟡 No audit trail

### Production Phase (🚨 UNACCEPTABLE)
- 🔴 Database breach risk from internet
- 🔴 No network security boundaries
- 🔴 Compliance violations (GDPR, SOX, etc.)
- 🔴 No incident response capabilities

## 🛠️ IMMEDIATE FIXES REQUIRED

### Fix 1: Secure Cloud SQL Database 🔴 CRITICAL

**Problem**: Database accessible from internet without IP restrictions.

**Solution A**: Enable VPC and Private IP (Recommended)
```hcl
# Update variables.tf
variable "use_vpc" {
  default = true  # Change from false to true
}

# This will create:
# - Private VPC network
# - Private IP for Cloud SQL
# - VPC connector for Cloud Run
```

**Solution B**: Add IP Restrictions (Quick Fix)
```hcl
# In cloud_sql.tf - add authorized networks
resource "google_sql_database_instance" "main" {
  settings {
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "cloud-run-egress"
        value = "0.0.0.0/0"  # Replace with actual Cloud Run egress IPs
      }
      require_ssl = true  # Force SSL connections
    }
  }
  deletion_protection = true  # Prevent accidental deletion
}
```

### Fix 2: Secure Database Credentials 🟡 HIGH PRIORITY

**Problem**: Password in plain text environment variables.

**Solution**: Use Secret Manager
```hcl
# Add to main.tf
resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

# Update cloud_run.tf
env {
  name = "DB_PASSWORD"
  value_from {
    secret_key_ref {
      name = google_secret_manager_secret.db_password.secret_id
      key  = "latest"
    }
  }
}
```

### Fix 3: Create Dedicated Service Account 🟡 MEDIUM PRIORITY

**Problem**: Using overprivileged default service account.

**Solution**: Least-privilege custom service account
```hcl
# Replace iam.tf content:
resource "google_service_account" "backend" {
  account_id   = "backend-sa"
  display_name = "Backend Service Account"
  project      = google_project.project.project_id
}

# Minimal required permissions
resource "google_project_iam_member" "backend_cloudsql_client" {
  project = google_project.project.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_logs_writer" {
  project = google_project.project.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_secret_accessor" {
  project = google_project.project.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# Update cloud_run.tf
service_account_name = google_service_account.backend.email
```

### Fix 4: Restrict Cloud Run Access (Choose One)

**Option A**: Authenticated Users Only (Recommended for MVP)
```hcl
# In cloud_run.tf - replace the existing resource
resource "google_cloud_run_service_iam_member" "authenticated" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allAuthenticatedUsers"  # Only authenticated Google users
}
```

**Option B**: Service Account Based (Production Ready)
```hcl
# Create frontend service account in iam.tf
resource "google_service_account" "frontend" {
  account_id   = "frontend-sa"
  display_name = "Frontend Service Account"
  project      = google_project.project.project_id
}

# In cloud_run.tf - replace the existing resource
resource "google_cloud_run_service_iam_member" "frontend" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend.email}"
}
```

**Option C**: Keep Public for POC (Document Risk)
```hcl
# Keep current setup but add monitoring
resource "google_cloud_run_service_iam_member" "public" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
  # TODO: Replace before production - see post_setup_todo.md
}
```

## 📋 IMPLEMENTATION PRIORITY MATRIX

### 🚨 CRITICAL (Fix Immediately)
**Timeline**: Before any external demo/testing
1. **Enable VPC + Private SQL** (`use_vpc = true`)
2. **Enable deletion protection** (`deletion_protection = true`)
3. **Move DB password to Secret Manager**

### 🔴 HIGH (Fix Before MVP)
**Timeline**: Before user acceptance testing
1. **Create dedicated service account**
2. **Restrict Cloud Run access** (choose Option A or B above)
3. **Enable SQL SSL requirements**
4. **Add audit logging**

### 🟡 MEDIUM (Fix Before Production)
**Timeline**: Before public launch
1. **Implement API rate limiting**
2. **Add Cloud Armor protection**
3. **Set up monitoring alerts**
4. **Review and minimize IAM permissions**

### 🟢 LOW (Production Optimization)
**Timeline**: Post-launch improvements
1. **Consider API Gateway**
2. **Implement custom encryption keys**
3. **Add network access logging**
4. **Set up automated security scanning**

## 🛡️ ADDITIONAL SECURITY RECOMMENDATIONS

### Enable Audit Logging
```hcl
# Add to main.tf
resource "google_logging_project_sink" "audit_logs" {
  name        = "audit-logs-sink"
  destination = "storage.googleapis.com/${google_storage_bucket.audit_logs.name}"
  filter      = "protoPayload.serviceName=\"cloudresourcemanager.googleapis.com\" OR protoPayload.serviceName=\"cloudsql.googleapis.com\" OR protoPayload.serviceName=\"run.googleapis.com\""
}
```

### Add Monitoring Alerts
```hcl
# Add to main.tf
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "High Error Rate"
  conditions {
    display_name = "Error rate too high"
    condition_threshold {
      filter         = "resource.type=\"cloud_run_revision\""
      comparison     = "COMPARISON_GREATER_THAN"
      threshold_value = 0.1
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.name]
}
```

### Enable SQL Connection Encryption
```hcl
# Update cloud_sql.tf
resource "google_sql_database_instance" "main" {
  settings {
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    ip_configuration {
      require_ssl = true
      ssl_mode    = "ENCRYPTED_ONLY"
    }
  }
}
```

## 🧪 SECURITY TESTING CHECKLIST

### Database Security Tests
```bash
# Test 1: Verify database is not publicly accessible
nmap -p 5432 <YOUR_SQL_PUBLIC_IP>  # Should timeout or be filtered

# Test 2: Verify SSL is required
psql "host=<YOUR_SQL_IP> user=<USER> dbname=<DB> sslmode=disable"  # Should fail

# Test 3: Verify Cloud SQL Auth Proxy works
cloud_sql_proxy -instances=<CONNECTION_NAME>=tcp:5432 &
psql "host=127.0.0.1 user=<USER> dbname=<DB>"  # Should work
```

### API Security Tests
```bash
# Test 1: Verify public access (if keeping for POC)
curl https://your-cloud-run-url.run.app/health  # Should work

# Test 2: After implementing auth - no token should fail
curl https://your-cloud-run-url.run.app/api/v1/protected  # Should return 401

# Test 3: With valid token should work
curl -H "Authorization: Bearer $ID_TOKEN" https://your-cloud-run-url.run.app/api/v1/protected
```

### Service Account Tests
```bash
# Test 1: Verify custom service account is used
gcloud run services describe <SERVICE_NAME> --region=<REGION> | grep serviceAccountName

# Test 2: Verify minimal permissions
gcloud projects get-iam-policy <PROJECT_ID> --flatten="bindings[].members" --filter="bindings.members:backend-sa"
```

## 📊 SECURITY MONITORING SETUP

### Essential Alerts to Configure
1. **Unusual Database Access Patterns**
2. **Failed Authentication Attempts**
3. **High API Error Rates**
4. **Unexpected Cloud Run Scaling**
5. **Terraform State File Access**

### Logging to Enable
```bash
# Enable audit logs for critical services
gcloud logging sinks create security-audit-sink \
  --log-filter='protoPayload.serviceName=("cloudsql.googleapis.com" OR "run.googleapis.com")' \
  --destination=storage.googleapis.com/your-security-logs-bucket
```

## 📋 PRODUCTION READINESS CHECKLIST

### Before Going Live
- [ ] 🔴 Enable VPC + Private SQL
- [ ] 🔴 Move passwords to Secret Manager  
- [ ] 🔴 Create dedicated service accounts
- [ ] 🔴 Restrict Cloud Run access
- [ ] 🔴 Enable deletion protection
- [ ] 🟡 Add rate limiting to FastAPI
- [ ] 🟡 Set up monitoring alerts
- [ ] 🟡 Review all IAM permissions
- [ ] 🟡 Enable audit logging
- [ ] 🟢 Add Cloud Armor protection
- [ ] 🟢 Implement backup strategy
- [ ] 🟢 Security penetration testing

### Compliance Considerations
- **GDPR**: Audit logging, data encryption, right to deletion
- **SOX**: Access controls, audit trails, segregation of duties  
- **PCI**: If handling payments - additional network isolation required
- **ISO 27001**: Risk assessment, incident response procedures

## 🚨 IMMEDIATE ACTION REQUIRED

**The most critical issue is your Cloud SQL database being publicly accessible without IP restrictions.**

**Quick Fix for Today**:
1. Set `use_vpc = true` in `terraform.tfvars`
2. Run `terraform plan` and `terraform apply`
3. This will create private networking and secure your database

**Time Investment**:
- **Critical fixes**: 2-4 hours
- **High priority fixes**: 1-2 days  
- **Medium priority fixes**: 3-5 days
- **Full production hardening**: 1-2 weeks

---

**Current Risk Level**: 🔴 **HIGH** (Database publicly accessible)  
**Target Risk Level**: 🟡 **MEDIUM** (After implementing critical fixes)  
**Production Risk Level**: 🟢 **LOW** (After full hardening)
