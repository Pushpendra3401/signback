output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "token_server_url" {
  description = "Public URL of the deployed Token Server Cloud Run service"
  value       = google_cloud_run_v2_service.token_server.uri
}

output "ai_server_url" {
  description = "Public URL of the deployed AI Server Cloud Run service"
  value       = google_cloud_run_v2_service.ai_server.uri
}

output "backend_service_account" {
  description = "Email of the service account used by both backend services"
  value       = google_service_account.signspeak_backend.email
}
