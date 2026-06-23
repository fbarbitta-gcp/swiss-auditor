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
  description = "The ID of the Google Cloud project"
  type        = string
}

variable "region" {
  description = "The region for AlloyDB"
  type        = string
}

variable "cluster_id" {
  description = "The ID of the AlloyDB cluster"
  type        = string
  default     = "swiss-auditor-cluster"
}

variable "instance_id" {
  description = "The ID of the AlloyDB primary instance"
  type        = string
  default     = "swiss-auditor-primary"
}

variable "db_password" {
  description = "AlloyDB initial user password"
  type        = string
  sensitive   = true
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
  description = "The name of the Shared VPC subnet to create the PSC endpoint in"
  type        = string
}
