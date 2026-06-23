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

variable "project_name" {
  description = "The name of the GCP Service Project."
  type        = string
}

variable "project_id" {
  description = "Optional explicit Project ID. If not provided, one will be generated dynamically."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "The Google Cloud Folder ID to create the service project under (without 'folders/' prefix)."
  type        = string
}

variable "billing_account_id" {
  description = "The Google Cloud Billing Account ID for the service project."
  type        = string
}

variable "host_project_id" {
  description = "The ID of the Host Project where the Shared VPC lives."
  type        = string
}
