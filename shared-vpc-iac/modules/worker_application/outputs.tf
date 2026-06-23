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

output "cloud_run_service_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.worker.uri
}

output "shared_vpc_network_id" {
  description = "The ID of the Shared VPC network"
  value       = data.google_compute_network.shared_vpc.id
}

output "shared_vpc_subnet_id" {
  description = "The ID of the Shared VPC subnet"
  value       = data.google_compute_subnetwork.shared_vpc_subnet.id
}

output "pubsub_invoker_sa_email" {
  description = "The email of the dedicated Pub/Sub invoker service account"
  value       = google_service_account.pubsub_invoker_sa.email
}
