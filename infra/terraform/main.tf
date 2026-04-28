terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable required GCP APIs ─────────────────────────────────────────────────
resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "firestore" {
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# ── Service Account for backend services ─────────────────────────────────────
resource "google_service_account" "signspeak_backend" {
  account_id   = "signspeak-backend"
  display_name = "SignSpeak Backend Service Account"
}

resource "google_project_iam_member" "backend_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.signspeak_backend.email}"
}

resource "google_project_iam_member" "backend_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.signspeak_backend.email}"
}

resource "google_project_iam_member" "backend_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.signspeak_backend.email}"
}

# ── Secret: Agora App Certificate ─────────────────────────────────────────────
resource "google_secret_manager_secret" "agora_cert" {
  secret_id = "agora-app-certificate"
  replication {
    auto {}
  }
}

# ── Cloud Run: Token Server ───────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "token_server" {
  name     = "signspeak-token-server"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.signspeak_backend.email

    containers {
      image = var.token_server_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "FIREBASE_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "TOKEN_TTL_SECONDS"
        value = "3600"
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name = "AGORA_APP_CERTIFICATE"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.agora_cert.secret_id
            version = "latest"
          }
        }
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.run]
}

# ── Cloud Run: AI Server ──────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "ai_server" {
  name     = "signspeak-ai-server"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.signspeak_backend.email

    containers {
      image = var.ai_server_image

      ports {
        container_port = 8081
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "FIREBASE_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "FIREBASE_STORAGE_BUCKET"
        value = "${var.project_id}.appspot.com"
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name  = "EMOTION_BACKEND"
        value = "opencv"
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.run]
}

# ── Allow unauthenticated invocations (Firebase auth handles it at app layer) ─
resource "google_cloud_run_service_iam_member" "token_server_public" {
  location = google_cloud_run_v2_service.token_server.location
  project  = var.project_id
  service  = google_cloud_run_v2_service.token_server.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "ai_server_public" {
  location = google_cloud_run_v2_service.ai_server.location
  project  = var.project_id
  service  = google_cloud_run_v2_service.ai_server.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
