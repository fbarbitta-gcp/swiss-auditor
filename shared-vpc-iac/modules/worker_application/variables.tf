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

variable "project_id" {
  description = "The ID of the Google Cloud project where resources will be deployed"
  type        = string
}

variable "region" {
  description = "The chosen region for Cloud Run and other regional resources"
  type        = string
  default     = "southamerica-east1"
}

variable "developer_members" {
  description = "List of IAM members who should have developer access (e.g. ['user:dev@example.com'])"
  type        = list(string)
  default     = []
}

variable "shared_vpc_project" {
  description = "The project ID of the Shared VPC Host"
  type        = string
}

variable "shared_vpc_network" {
  description = "The name of the Shared VPC network"
  type        = string
}

variable "shared_vpc_subnet" {
  description = "The name of the Shared VPC subnet to connect to"
  type        = string
}

variable "service_name" {
  description = "The name of the Cloud Run service"
  type        = string
  default     = "swiss-auditor-worker"
}

variable "image" {
  description = "The docker image to deploy for Cloud Run. If not provided, it defaults to the hello-world placeholder for initial Terraform bootstrapping."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

# Production scaling variables
variable "min_instance_count" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 20
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 1
}

variable "timeout_seconds" {
  description = "Timeout for Cloud Run requests in seconds"
  type        = number
  default     = 3600
}

variable "bucket_name" {
  description = "Name of the storage bucket for resource-level IAM binding"
  type        = string
  default     = null
}

variable "secret_ids" {
  description = "List of Secret Manager secret IDs for resource-level IAM binding"
  type        = list(string)
  default     = []
}

variable "alloydb_cluster_id" {
  description = "The ID of the AlloyDB cluster for resource-level IAM binding"
  type        = string
  default     = null
}
