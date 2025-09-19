# Enable required GCP APIs
resource "google_project_service" "cloud_run_api" {
  project = google_project.project.project_id
  service = "run.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "sql_admin_api" {
  project = google_project.project.project_id
  service = "sqladmin.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "artifact_registry_api" {
  project = google_project.project.project_id
  service = "artifactregistry.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "cloud_build_api" {
  project = google_project.project.project_id
  service = "cloudbuild.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "cloud_logging_api" {
  project = google_project.project.project_id
  service = "logging.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "cloud_monitoring_api" {
  project = google_project.project.project_id
  service = "monitoring.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "secret_manager_api" {
  project = google_project.project.project_id
  service = "secretmanager.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "compute_api" {
  project = google_project.project.project_id
  service = "compute.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "firebase_api" {
  project = google_project.project.project_id
  service = "firebase.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_service" "firebase_hosting_api" {
  project = google_project.project.project_id
  service = "firebasehosting.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy         = false
}
