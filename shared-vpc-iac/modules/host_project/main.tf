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

# 0. Enable APIs on host project
resource "google_project_service" "host_compute" {
  project            = var.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

# 1. Configure the Host Project and VPC
module "shared_vpc" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-vpc?ref=master"
  project_id = var.project_id
  name       = var.vpc_name

  depends_on = [google_project_service.host_compute]

  # Enable the Shared VPC Host feature on the project
  shared_vpc_host = true

  subnets = [
    {
      name          = "subnet-apps-01"
      region        = var.region
      ip_cidr_range = "10.10.0.0/24"
    }
  ]
}
