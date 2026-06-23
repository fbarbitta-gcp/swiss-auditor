# Swiss Auditor - Deployment Guide

This guide details the infrastructure, permissions, and configuration required to deploy the Swiss Auditor system to Google Cloud.

## 1. Prerequisites

### Google Cloud Resources
*   **Project**: A Google Cloud Project with billing enabled.
*   **Networking**: A VPC network with a subnet dedicated for Cloud Run Direct VPC Egress.
    *   *Note*: The `cloudbuild.yaml` references `shared-vpc-argolis` and `subnet-apps-01`. Ensure these exist.
*   **AlloyDB**: A PostgreSQL AlloyDB instance reachable from the configured VPC.
*   **Secret Manager**: Secrets created to store sensitive DB credentials.

### Required APIs
Enable the following APIs:
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  alloydb.googleapis.com \
  pubsub.googleapis.com \
  storage.googleapis.com
```

## 2. Service Account & IAM Permissions

### Grant Permissions to Compute Engine Service Account

Instead of creating a new Service Account, we will use the default Compute Engine Service Account.

First, retrieve the default Service Account email:
```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

Grant the **strictly required** roles:
```bash
# 1. GCS Access (Read/Write documents & results)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/storage.objectAdmin"

# 2. Vertex AI User (For Gemini 2.5 Flash)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/aiplatform.user"

# 3. Secret Manager Access (For DB Credentials)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
```

### Pub/Sub Invoker
The **Pub/Sub Service Agent** needs permission to invoke your Cloud Run service:
```bash
# Get the Pub/Sub service agent email
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
PUBSUB_SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

# Grant the role
gcloud run services add-iam-policy-binding swiss-auditor-worker \
    --member="serviceAccount:${PUBSUB_SERVICE_ACCOUNT}" \
    --role="roles/run.invoker" \
    --region="southamerica-east1" # Update to your region
```

## 3. Configuration & Secrets

### Secret Manager
The `cloudbuild.yaml` expects the following secrets to exist in **Secret Manager**:
1.  **`db-password`**: The password for the PostgreSQL user.
2.  **`db-host`**: The private IP address of the AlloyDB instance.
3.  **`db-user`**: The PostgreSQL username (e.g., `postgres`).
4.  **`db-name`**: The database name (e.g., `postgres`).

Create them using:
```bash
echo -n "YOUR_PASSWORD" | gcloud secrets create db-password --data-file=-
# Repeat for others...
```

### Build & Deploy
The `cloudbuild.yaml` is configured for **Direct VPC Egress**.

**Important**: 
*   Update `substitutions` in `cloudbuild.yaml` if you are not using `southamerica-east1`.
*   Ensure `cloudbuild.yaml` is pointing to the correct VPC/subnet.

```yaml
# Existing arguments in cloudbuild.yaml step 3 should be sufficient if using default SA.
```

## 4. Environment Variables

The application can be configured via `.env` for local runs, but for Cloud Run, ensure the following are passed (some are already handled via Secrets):
*   `GOOGLE_GENAI_USE_VERTEXAI`: Set to `"true"`.
*   `GOOGLE_CLOUD_PROJECT`: Should be set automatically by Cloud Run, but good to verify.
*   `GOOGLE_CLOUD_LOCATION`: Region for Vertex AI (e.g., `us-central1`).

## 5. Deployment Steps

1.  **Clone the repo**.
2.  **Update `cloudbuild.yaml`** with your specific VPC/Subnet names if they differ from `shared-vpc-argolis`.
3.  **Ensure Secrets** are created.
4.  **Submit Build**:
    ```bash
    ```

## 6. Vertex AI Agent Engine (Enterprise) Deployment

For deploying the high-level **Gemini Enterprise Agent** with support for Direct VPC Egress/PSC, see:
*   [Connecting a Gemini Enterprise Agent to VPC via PSC](AGENT_ENGINE_PSC.md)

This details how to connect the agent to AlloyDB using a PSC Network Attachment configured via `.env` adjustments.
