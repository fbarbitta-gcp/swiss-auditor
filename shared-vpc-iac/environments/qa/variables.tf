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

variable "host_project_id" {
  description = "The ID of the GCP Host Project where the VPC will be created."
  type        = string
}

variable "vpc_name" {
  description = "The name of the Shared VPC."
  type        = string
  default     = "my-shared-network"
}

variable "region" {
  description = "The GCP region to deploy resources."
  type        = string
  default     = "us-central1"
}

variable "service_project_name" {
  description = "The name of the GCP Service Project."
  type        = string
}

variable "folder_id" {
  description = "The Google Cloud Folder ID to create the service project under (without 'folders/' prefix)."
  type        = string
}

variable "billing_account_id" {
  description = "The Google Cloud Billing Account ID for the service project."
  type        = string
}

variable "service_project_id" {
  description = "Optional custom Project ID for the service project."
  type        = string
  default     = null
}

variable "shared_vpc_subnet" {
  description = "The name of the Shared VPC subnet to connect the application to."
  type        = string
}

variable "db_password" {
  description = "Initial password for the AlloyDB database."
  type        = string
  sensitive   = true
}
