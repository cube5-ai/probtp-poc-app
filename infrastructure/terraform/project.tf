# GCP Project creation and billing attachment

resource "google_project" "project" {
  name       = "PRO BTP POC - Prod"
  project_id = var.project_id
  org_id     = var.org_id
  billing_account = var.billing_account_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}


