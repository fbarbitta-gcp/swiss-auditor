# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

resource "google_cloud_run_v2_service" "worker" {
  name                = var.service_name
  location            = var.region
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Adjust if external ingress is needed
  deletion_protection = false

  template {
    service_account = google_service_account.worker_sa.email
    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1000m" # Based on --no-cpu-throttling being set in previous deploy but implicit CPU, adjust as needed. Often 1000m or 2000m.
          memory = "4Gi"
        }
        cpu_idle = false # --no-cpu-throttling
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }

      # Secrets mounted as environment variables
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = "db-password"
            version = "latest"
          }
        }
      }
      env {
        name = "DB_HOST"
        value_source {
          secret_key_ref {
            secret  = "db-host"
            version = "latest"
          }
        }
      }
      env {
        name = "DB_USER"
        value_source {
          secret_key_ref {
            secret  = "db-user"
            version = "latest"
          }
        }
      }
      env {
        name = "DB_NAME"
        value_source {
          secret_key_ref {
            secret  = "db-name"
            version = "latest"
          }
        }
      }
    }

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    max_instance_request_concurrency = var.concurrency
    timeout                          = "${var.timeout_seconds}s"

    # Connect to the Shared VPC via Direct VPC Egress
    vpc_access {
      network_interfaces {
        network    = data.google_compute_network.shared_vpc.id
        subnetwork = data.google_compute_subnetwork.shared_vpc_subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY" # Matches --vpc-egress=private-ranges-only
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }

  depends_on = [
    google_project_iam_member.worker_secret_access
  ]
}
