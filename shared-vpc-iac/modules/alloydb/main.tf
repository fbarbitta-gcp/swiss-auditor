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

data "google_compute_network" "shared_vpc" {
  name    = var.shared_vpc_network
  project = var.shared_vpc_project
}

data "google_compute_subnetwork" "shared_vpc_subnet" {
  name    = var.shared_vpc_subnet
  project = var.shared_vpc_project
  region  = var.region
}

data "google_project" "service_project" {
  project_id = var.project_id
}

resource "google_alloydb_cluster" "default" {
  cluster_id          = var.cluster_id
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  initial_user {
    user     = "postgres"
    password = var.db_password
  }

  psc_config {
    psc_enabled               = true
  }
}

resource "google_alloydb_instance" "primary" {
  cluster       = google_alloydb_cluster.default.name
  instance_id   = var.instance_id
  instance_type = "PRIMARY"

  machine_config {
    cpu_count = 2
  }

  psc_instance_config {
    allowed_consumer_projects = [data.google_project.service_project.number]
  }
}

resource "google_compute_address" "psc_ip" {
  name         = "alloydb-psc-ip"
  project      = var.project_id
  region       = var.region
  subnetwork   = data.google_compute_subnetwork.shared_vpc_subnet.id
  address_type = "INTERNAL"
}

resource "google_compute_forwarding_rule" "psc_endpoint" {
  name                    = "alloydb-psc-endpoint"
  project                 = var.project_id
  region                  = var.region
  network                 = data.google_compute_network.shared_vpc.id
  load_balancing_scheme   = ""
  target                  = google_alloydb_instance.primary.psc_instance_config[0].service_attachment_link
  ip_address              = google_compute_address.psc_ip.id
  allow_psc_global_access = true
}
