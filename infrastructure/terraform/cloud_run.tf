# Cloud Run service for FastAPI backend
resource "google_cloud_run_service" "backend" {
  name     = "${local.project_name}-backend-${local.environment}"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/${local.project_name}-backend:latest"
        
        ports {
          container_port = 8000
        }

        env {
          name  = "DATABASE_URL"
          value = "postgresql://${google_sql_user.backend.name}:${google_sql_user.backend.password}@${google_sql_database_instance.main.connection_name}/${google_sql_database.main.name}"
        }

        env {
          name  = "ENVIRONMENT"
          value = local.environment
        }

        env {
          name  = "REDIS_URL"
          value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}"
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
