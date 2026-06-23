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

variable "db_password" {
  description = "Initial password for the database. Note: subsequent changes should be done via Secret Manager UI or CLI."
  type        = string
  sensitive   = true
}

variable "db_host" {
  description = "Initial host (IP) for the database. Note: subsequent changes should be done via Secret Manager UI or CLI."
  type        = string
}

variable "db_user" {
  description = "Initial user for the database. Note: subsequent changes should be done via Secret Manager UI or CLI."
  type        = string
  default     = "postgres"
}

variable "db_name" {
  description = "Initial database name. Note: subsequent changes should be done via Secret Manager UI or CLI."
  type        = string
  default     = "postgres"
}
