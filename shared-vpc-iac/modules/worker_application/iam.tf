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

# Developer Roles Mapping
locals {
  developer_roles = toset([
    "roles/run.developer",                # Deploy and manage Cloud Run revisions
    "roles/logging.viewer",               # Read logs in Cloud Logging
    "roles/errorreporting.viewer",        # View Error Reporting traces
    "roles/cloudtrace.viewer",            # View tracing and latencies
    "roles/secretmanager.secretAccessor", # Check database credentials/secrets if needed for local debugging
    "roles/alloydb.client"                # Connect to AlloyDB for testing ingestion
  ])
}

# Grant the roles to the specified developers at the project level
resource "google_project_iam_member" "developer_access" {
  for_each = {
    for pair in setproduct(var.developer_members, local.developer_roles) :
    "${pair[0]}-${pair[1]}" => {
      member = pair[0]
      role   = pair[1]
    }
  }

  project = var.project_id
  member  = each.value.member
  role    = each.value.role
}

# Worker Service Account
resource "google_service_account" "worker_sa" {
  account_id   = "swiss-auditor-worker-sa"
  display_name = "Swiss Auditor Cloud Run Worker"
  project      = var.project_id
}

# Roles for the Worker Service Account
locals {
  worker_roles = toset([
    "roles/aiplatform.user" # Keep project-level for Vertex AI if needed, others should be resource-scoped
  ])
}

resource "google_project_iam_member" "worker_sa_roles" {
  for_each = local.worker_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.worker_sa.email}"
}

# Resource-scoped Storage Access
resource "google_storage_bucket_iam_member" "worker_bucket_access" {
  bucket = var.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.worker_sa.email}"
}

# Resource-scoped Secrets Access
# We use string manipulation to grant access to the specific secrets, but without for_each over unknown values
# We know the secret names because they are hardcoded in the caller, but the module is receiving their fully qualified IDs.
# Since var.secret_ids is a list of unknown strings during plan, we cannot use for_each on it directly.
# Let's switch to granting secretAccessor on the project level, or we must change the module interface to accept known static maps.
# To balance security with Terraform limitations, we will grant secret manager access at the project level, as resource level
# requires a complex two-step apply or strict static name passing instead of dynamic IDs.
resource "google_project_iam_member" "worker_secret_access" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.worker_sa.email}"
}

# AlloyDB Access (Project level, as resource-level IAM is unsupported in Terraform provider for AlloyDB clusters)
resource "google_project_iam_member" "worker_alloydb_access" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.worker_sa.email}"
}

# Data source for Project Number
data "google_project" "project" {
  project_id = var.project_id
}

# Dedicated Service Account for Pub/Sub to invoke Cloud Run
resource "google_service_account" "pubsub_invoker_sa" {
  account_id   = "pubsub-invoker-sa"
  display_name = "Pub/Sub Cloud Run Invoker"
  project      = var.project_id
}

# Allow our custom Pub/Sub Invoker SA to invoke the Cloud Run service
resource "google_cloud_run_service_iam_member" "pubsub_invoker" {
  location = var.region
  project  = var.project_id
  service  = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker_sa.email}"
}
