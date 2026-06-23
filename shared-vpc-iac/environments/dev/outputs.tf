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

output "host_project_id" {
  description = "The ID of the host project."
  value       = var.host_project_id
}

output "shared_vpc_name" {
  description = "The name of the Shared VPC."
  value       = var.vpc_name
}

output "service_project_id" {
  description = "The ID of the main service project."
  value       = module.service_project.project_id
}

output "cloud_run_service_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = module.worker_application.cloud_run_service_url
}
