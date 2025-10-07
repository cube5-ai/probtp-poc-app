# Service account for Cloud Run backend
resource "google_service_account" "cloud_run_backend" {
  account_id   = "${local.project_name}-backend-sa-${local.environment}"
  display_name = "Cloud Run Backend Service Account"
  description  = "Service account for Cloud Run backend to access Cloud SQL and other resources"
}

# Grant Cloud SQL Client role to service account
resource "google_project_iam_member" "cloud_run_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_backend.email}"
}

# Cloud Run service for FastAPI backend
resource "google_cloud_run_service" "backend" {
  name     = "${local.project_name}-backend-${local.environment}"
  location = var.region

  template {
    spec {
      # Enable Cloud SQL Proxy sidecar
      service_account_name = google_service_account.cloud_run_backend.email
      
      containers {
        image = "gcr.io/${var.project_id}/${local.project_name}-backend:latest"
        
        ports {
          container_port = 8000
        }

        startup_probe {
          http_get {
            path = "/api/v1/health"
            port = 8000
          }
          initial_delay_seconds = 10
          timeout_seconds       = 3
          period_seconds        = 5
          failure_threshold     = 10
        }

        liveness_probe {
          http_get {
            path = "/api/v1/health"
            port = 8000
          }
          initial_delay_seconds = 30
          timeout_seconds       = 3
          period_seconds        = 10
        }

        env {
          name  = "ENVIRONMENT"
          value = local.environment
        }

        env {
          name  = "DB_USER"
          value = google_sql_user.backend.name
        }

        env {
          name  = "DB_PASSWORD"
          value = google_sql_user.backend.password
        }

        env {
          name  = "DB_NAME"
          value = google_sql_database.main.name
        }

        env {
          name  = "CLOUD_SQL_CONNECTION_NAME"
          value = google_sql_database_instance.main.connection_name
        }

        env {
          name  = "REDIS_URL"
          value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}"
        }

        env {
          name  = "FIREBASE_PROJECT_ID"
          value = var.project_id
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }

    metadata {
      annotations = {
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.main.connection_name
        "run.googleapis.com/client-name"        = "terraform"
      }
      labels = local.common_labels
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.cloud_run_api]
}

# IAM policy for Cloud Run service
resource "google_cloud_run_service_iam_member" "public" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
