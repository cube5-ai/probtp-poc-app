# Cloud Run service for FastAPI backend
resource "google_cloud_run_service" "backend" {
  name     = "${local.project_name}-backend-${local.environment}"
  location = var.region

  template {
    spec {
      service_account_name = "${google_project.project.number}-compute@developer.gserviceaccount.com"
      containers {
        image = "${google_artifact_registry_repository.containers.location}-docker.pkg.dev/${google_project.project.project_id}/${google_artifact_registry_repository.containers.repository_id}/${local.project_name}-backend:${var.backend_image_tag}"

        ports {
          container_port = 8000
        }

        env {
          name  = "ENVIRONMENT"
          value = local.environment
        }

        # REDIS_URL omitted for POC (no Redis)

        env {
          name  = "DB_INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.main.connection_name
        }

        env {
          name  = "DB_NAME"
          value = google_sql_database.main.name
        }

        env {
          name  = "DB_USER"
          value = google_sql_user.backend.name
        }

        env {
          name  = "DB_PASSWORD"
          value = var.db_password
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "2Gi"
          }
        }
      }

      container_concurrency = 100

    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"         = "0"
        "autoscaling.knative.dev/maxScale"         = "5"
        "run.googleapis.com/cloudsql-instances"     = google_sql_database_instance.main.connection_name
      }
      labels = local.common_labels
    }
  }

  # Service-level annotations (not on Revision)
  metadata {
    annotations = {
      "run.googleapis.com/ingress" = "all"
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.cloud_run_api,
    google_artifact_registry_repository.containers
  ]
}

# IAM policy for Cloud Run service
resource "google_cloud_run_service_iam_member" "public" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
