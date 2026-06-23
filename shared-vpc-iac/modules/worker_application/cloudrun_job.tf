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

resource "google_cloud_run_v2_job" "retry_job" {
  name     = "${var.service_name}-retry"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # This image will be overwritten by Cloud Build once the retry_job container is built.
        # We use var.image as a safe placeholder for initial terraform apply.
        image = var.image
        
        env {
          name  = "BUCKET_NAME"
          value = var.bucket_name == null ? "liquidacionesraw" : var.bucket_name
        }
        env {
          name  = "AGE_HOURS"
          value = "2.0"
        }
      }
      service_account = google_service_account.worker_sa.email
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  location = google_cloud_run_v2_job.retry_job.location
  project  = google_cloud_run_v2_job.retry_job.project
  name     = google_cloud_run_v2_job.retry_job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker_sa.email}"
}
