# Variables for GCP infrastructure
variable "org_id" {
  description = "GCP Organization ID (e.g., 518110912541)"
  type        = string
}

variable "billing_account_id" {
  description = "GCP Billing Account ID (e.g., 000000-000000-000000)"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID to create and manage (e.g., probtp-poc-prod)"
  type        = string
}

variable "region" {
  description = "Primary region for resources (e.g., europe-west9 for Paris)"
  type        = string
  default     = "europe-west9"
}

variable "zone" {
  description = "Primary zone (e.g., europe-west9-a)"
  type        = string
  default     = "europe-west9-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "firebase_project_id" {
  description = "Firebase project ID (can be same as GCP project_id)"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "db_password" {
  description = "Database password for the backend user"
  type        = string
  sensitive   = true
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository name for containers"
  type        = string
  default     = "containers"
}

variable "backend_image_tag" {
  description = "Container image tag for backend (e.g., v1.0.0)"
  type        = string
  default     = "latest"
}

variable "create_firebase_project" {
  description = "Whether to create/initialize Firebase project bindings"
  type        = bool
  default     = false
}

# VPC and Redis are intentionally not supported for the POC to keep it simple
