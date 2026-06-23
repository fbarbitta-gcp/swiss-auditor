# Swiss Auditor - Shared VPC & Infrastructure Deployment

This repository contains the Terraform Infrastructure as Code (IaC) to deploy the complete **Swiss Auditor** architecture on Google Cloud within a Shared VPC. It utilizes the [Google Cloud Foundation Fabric (CFF)](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) modules along with custom modules for the application stack.

## Architecture Overview

The deployment creates a Host Project with a Shared VPC and a connected Service Project containing:
*   **Google Cloud Storage**: For document ingestion and results.
*   **AlloyDB (PostgreSQL)**: Connected via Private Service Connect (PSC).
*   **Secret Manager**: For managing database credentials.
*   **Pub/Sub**: For receiving dispatch events and pushing them to the worker.
*   **Cloud Run (Worker Application)**: The core AI processing service, running with a dedicated Service Account.

## Prerequisites

1.  **Terraform**: Ensure you have Terraform installed (version 1.0+ recommended).
2.  **Google Cloud SDK (`gcloud`)**: Installed and authenticated with an account capable of creating projects, networks, and IAM bindings.

Authenticate Terraform to Google Cloud by running:
```bash
gcloud auth application-default login
```

## Configuration

Deployments are structured using environments (`environments/dev/`).

Before deploying, configure your variables:

1.  Navigate to the dev environment:
    ```bash
    cd environments/dev
    ```

2.  Copy or create a variable file (e.g., `terraform.tfvars`) and fill in your values. Note that `*.tfvars` files are ignored by git:
    *   `host_project_id`: Centralized project ID for the VPC.
    *   `vpc_name`: Name for your Shared VPC.
    *   `region`: Primary GCP region (e.g., `southamerica-east1`).
    *   `shared_vpc_subnet`: Name of the subnet to connect the application and AlloyDB PSC to.
    *   `folder_id`: GCP Folder ID where the service project will reside (numeric).
    *   `billing_account_id`: GCP Billing Account ID (XXXXXX-XXXXXX-XXXXXX).
    *   `service_project_name`: Name of the service project.
    *   `service_project_id`: (Optional) Explicit ID for the service project.
    *   `db_password`: Initial password for the AlloyDB `postgres` user.

## Deployment Steps

Deploying the Swiss Auditor architecture is a multi-step process involving infrastructure provisioning, application deployment, and database initialization.

### Step 1: Deploy Infrastructure (Terraform)
First, we deploy the network, database, buckets, and a placeholder Cloud Run service.

1.  **Initialize Terraform**
    ```bash
    cd environments/dev
    terraform init
    ```

2.  **Plan the Deployment**
    ```bash
    terraform plan
    ```

3.  **Apply the Configuration**
    ```bash
    terraform apply
    ```
    *Type `yes` when prompted to confirm.*

### Step 2: Build & Deploy the Application Container
Once the infrastructure exists, we must build the Python `worker_service` image and deploy it to the Terraform-created Cloud Run service. 
This is handled natively via Cloud Build.

From the **root** of the repository (where `cloudbuild.yaml` is located), run:

```bash
gcloud builds submit --config cloudbuild.yaml --project <YOUR_SERVICE_PROJECT_ID> .
```
This process will:
1. Build the Docker image.
2. Push it to the `us-central1-docker.pkg.dev` Artifact Registry.
3. Automatically execute `gcloud run deploy` to update the worker service with the new image, connecting it securely to the Shared VPC.

### Step 3: Build & Deploy the Retry Job
The `swiss-auditor-worker-retry` Cloud Run Job is used to periodically scan for failed processes. Similar to the main worker, it must be deployed from its dedicated folder after Terraform provisions the job placeholder.

From the `retry_job/` folder, run:

```bash
cd retry_job/
gcloud builds submit --config cloudbuild.yaml --project <YOUR_SERVICE_PROJECT_ID> .
```
This process will build the retry container image, push it to Artifact Registry, and update the Cloud Run Job via `gcloud run jobs update` so that Cloud Scheduler can trigger it correctly.

### Step 4: Initialize the AlloyDB Database
The `worker_service` requires the `investigations` and `billing_items` tables to exist. 

Because AlloyDB is deployed in a Shared VPC with only a Private Service Connect (PSC) endpoint, it is **not accessible from the public internet**.
You must execute `schema.sql` from within the Google Cloud network.

1.  **Deploy a Jump Host:** Create a temporary Compute Engine VM in the Shared VPC `subnet-apps-01`.
2.  **Connect and Initialize:** SSH into the VM, install `postgresql-client`, and connect to the AlloyDB Private IP (e.g., `10.x.x.x`).
3.  **Run Schema:** Execute the contents of `schema.sql` against the `postgres` database.

### Step 5: Test the End-to-End Pipeline
The architecture is fully automated and event-driven via Google Cloud Storage notifications.

To trigger the pipeline:
1. Upload a dummy invoice or `.pdf` file to the generated storage bucket:
   ```bash
   gsutil cp test.pdf gs://<YOUR_BUCKET_NAME>/data/test_case_001/test.pdf
   ```
2. This upload will automatically publish an `OBJECT_FINALIZE` event to Pub/Sub.
3. Pub/Sub will instantly push the message payload to the Cloud Run `worker_service`.
4. The worker will process the document and write the results to your AlloyDB database.

You can verify the execution by checking the **Cloud Run Logs**.

## Outputs

After a successful deployment, Terraform will output:
*   `host_project_id`: The project ID of the host network.
*   `shared_vpc_name`: The name of the Shared VPC.
*   `service_project_id`: The ID of the service project containing the application.
*   `cloud_run_service_url`: The public URL of the deployed Cloud Run worker service.

## Clean Up

To tear down the infrastructure and remove the created projects and network:
```bash
terraform destroy
```
