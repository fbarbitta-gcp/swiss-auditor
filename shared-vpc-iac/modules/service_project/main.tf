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

# Generate a random suffix for global uniqueness
resource "random_id" "suffix" {
  byte_length = 4
}

# Configure the Service Project
module "service_project" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project?ref=master"

  # Name must be <= 30 chars. If project_id is provided, use it exactly as is. Otherwise generate one dynamically.
  name = coalesce(var.project_id, "${substr(var.project_name, 0, 21)}-${random_id.suffix.hex}")
  # If an explicit project_id is provided, use the descriptive project_name. Otherwise, let it default to the generated name.
  descriptive_name = var.project_id != null ? var.project_name : null

  parent          = "folders/${var.folder_id}"
  billing_account = var.billing_account_id

  services = [
    "compute.googleapis.com",
    "container.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "alloydb.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com"
  ]

  # Grant IAM roles natively in the project module
  iam = {
    "roles/storage.admin" = [
      "serviceAccount:${module.service_project.number}-compute@developer.gserviceaccount.com"
    ]
    "roles/artifactregistry.writer" = [
      "serviceAccount:${module.service_project.number}-compute@developer.gserviceaccount.com"
    ]
    "roles/run.admin" = [
      "serviceAccount:${module.service_project.number}-compute@developer.gserviceaccount.com"
    ]
    "roles/iam.serviceAccountUser" = [
      "serviceAccount:${module.service_project.number}-compute@developer.gserviceaccount.com"
    ]
    "roles/logging.logWriter" = [
      "serviceAccount:${module.service_project.number}-compute@developer.gserviceaccount.com"
    ]
  }

  # Attach the service project to the host project and set up permissions
  shared_vpc_service_config = {
    host_project = var.host_project_id

    # Grant specific Google-managed service agents access to the network
    service_agent_iam = {
      "roles/compute.networkUser" = [
        "cloudservices",
        "container-engine",
        "cloudrun"
      ]
    }
  }
}
