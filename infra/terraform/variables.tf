variable "project_id" {
  type        = string
  description = "GCP project ID (e.g. signspeak-20dff)"
}

variable "region" {
  type        = string
  description = "GCP region for Cloud Run deployments"
  default     = "us-central1"
}

variable "token_server_image" {
  type        = string
  description = "Docker image URI for the token server (e.g. gcr.io/PROJECT/token-server:latest)"
  default     = "gcr.io/signspeak-20dff/token-server:latest"
}

variable "ai_server_image" {
  type        = string
  description = "Docker image URI for the AI server (e.g. gcr.io/PROJECT/ai-server:latest)"
  default     = "gcr.io/signspeak-20dff/ai-server:latest"
}

variable "agora_app_id" {
  type        = string
  description = "Agora App ID (set via TF_VAR_agora_app_id or terraform.tfvars)"
  default     = ""
  sensitive   = true
}
