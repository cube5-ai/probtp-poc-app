# Cloud SQL PostgreSQL instance (public IP for POC simplicity)
resource "google_sql_database_instance" "main" {
  name             = "${local.project_name}-db-${local.environment}"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-g1-small"

    disk_autoresize       = true
    disk_autoresize_limit = 100
    disk_size             = 20
    disk_type             = "PD_SSD"

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = true
    }

    user_labels = local.common_labels
  }

  deletion_protection = false

  depends_on = [
    google_project_service.sql_admin_api
  ]
}

# Database
resource "google_sql_database" "main" {
  name     = "${local.project_name}_${local.environment}"
  instance = google_sql_database_instance.main.name
}

# Database user
resource "google_sql_user" "backend" {
  name     = "${local.project_name}_user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}
