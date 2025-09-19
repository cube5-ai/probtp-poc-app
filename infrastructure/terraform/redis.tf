# Redis instance for caching
resource "google_redis_instance" "cache" {
  name           = "${local.project_name}-redis-${local.environment}"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region

  auth_enabled   = false
  redis_version  = "REDIS_7_0"

  labels = local.common_labels

  depends_on = [google_project_service.redis_api]
}
