# Output values for GCP infrastructure
output "project_id" {
  description = "GCP Project ID"
  value       = google_project.project.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "cloud_run_backend_url" {
  description = "Backend Cloud Run service URL"
  value       = google_cloud_run_service.backend.status[0].url
}

output "firebase_hosting_url" {
  description = "Firebase Hosting URL"
  value       = "https://${var.firebase_project_id != "" ? var.firebase_project_id : google_project.project.project_id}.web.app"
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.main.connection_name
  sensitive   = true
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository path"
  value       = "${google_artifact_registry_repository.containers.location}-docker.pkg.dev/${google_project.project.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

# VPC connector not used in POC
