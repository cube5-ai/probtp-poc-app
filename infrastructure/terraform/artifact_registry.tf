# Artifact Registry repository for container images

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  description   = "Container images for PRO BTP POC"
  format        = "DOCKER"

  labels = local.common_labels

  depends_on = [
    google_project_service.artifact_registry_api
  ]
}

# Allow Cloud Run service account to pull images
resource "google_artifact_registry_repository_iam_member" "reader_cloud_run" {
  location   = google_artifact_registry_repository.containers.location
  repository = google_artifact_registry_repository.containers.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
}


