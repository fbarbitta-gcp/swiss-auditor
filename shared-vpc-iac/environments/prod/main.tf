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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}

provider "google" {
  region = var.region
}

# 1. Host Project configuring Shared VPC (Comentado - ya que reutilizamos el Spoke existente)
# module "host_project" {
#   source     = "../../modules/host_project"
#   project_id = var.host_project_id
#   vpc_name   = var.vpc_name
#   region     = var.region
# }

# 2. Service Project (attached to Shared VPC)
module "service_project" {
  source             = "../../modules/service_project"
  project_name       = var.service_project_name
  project_id         = var.service_project_id
  folder_id          = var.folder_id
  billing_account_id = var.billing_account_id
  host_project_id    = var.host_project_id
}

# 3. Deploy Worker Application within Service Project
module "worker_application" {
  source = "../../modules/worker_application"

  project_id         = module.service_project.project_id
  region             = var.region
  shared_vpc_project = var.host_project_id
  shared_vpc_network = var.vpc_name
  shared_vpc_subnet  = var.shared_vpc_subnet

  bucket_name        = module.storage.bucket_name
  secret_ids         = values(module.secrets.secret_ids)
  alloydb_cluster_id = module.alloydb.cluster_id

  image = "us-docker.pkg.dev/cloudrun/container/hello" # Placeholder image to bypass chicken-and-egg deployment issue

  depends_on = [module.service_project]
}

# Data source for Project Number to construct Pub/Sub SA
# data "google_project" "service_project" {
#   project_id = module.service_project.project_id
# }

# 4. Storage Bucket
module "storage" {
  source        = "../../modules/storage"
  project_id    = module.service_project.project_id
  region        = var.region
  force_destroy = true

  depends_on = [module.service_project]
}

# 5. AlloyDB Cluster
module "alloydb" {
  source             = "../../modules/alloydb"
  project_id         = module.service_project.project_id
  region             = var.region
  db_password        = var.db_password
  shared_vpc_project = var.host_project_id
  shared_vpc_network = var.vpc_name
  shared_vpc_subnet  = var.shared_vpc_subnet

  depends_on = [module.service_project]
}

# 6. Secret Manager Secrets
module "secrets" {
  source      = "../../modules/secrets"
  project_id  = module.service_project.project_id
  db_password = var.db_password
  db_host     = module.alloydb.psc_endpoint_ip
  db_user     = "postgres"
  db_name     = "postgres"

  depends_on = [module.service_project]
}

# 7. Pub/Sub Topic & Push Subscription
module "pubsub" {
  source                = "../../modules/pubsub"
  project_id            = module.service_project.project_id
  push_endpoint         = module.worker_application.cloud_run_service_url
  service_account_email = module.worker_application.pubsub_invoker_sa_email

  depends_on = [module.service_project]
}

# 8. Storage Notification to Pub/Sub
data "google_storage_project_service_account" "gcs_account" {
  project    = module.service_project.project_id
  depends_on = [module.service_project]
}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = module.pubsub.topic_id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_storage_notification" "notification" {
  bucket         = module.storage.bucket_name
  payload_format = "JSON_API_V1"
  topic          = module.pubsub.topic_id
  event_types    = ["OBJECT_FINALIZE"]
  depends_on     = [google_pubsub_topic_iam_member.gcs_publisher]
}

# State migrations for structural refactor
moved {
  from = google_project_service.host_compute
  to   = module.host_project.google_project_service.host_compute
}

moved {
  from = module.shared_vpc
  to   = module.host_project.module.shared_vpc
}

