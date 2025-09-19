# Minimum roles for backend to access Cloud SQL, logs, secret manager and monitoring
resource "google_project_iam_member" "backend_cloudsql_client" {
  project = google_project.project.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute_api]
}

resource "google_project_iam_member" "backend_logs_writer" {
  project = google_project.project.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute_api]
}

resource "google_project_iam_member" "backend_metric_writer" {
  project = google_project.project.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute_api]
}

resource "google_project_iam_member" "backend_secret_accessor" {
  project = google_project.project.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute_api]
}


