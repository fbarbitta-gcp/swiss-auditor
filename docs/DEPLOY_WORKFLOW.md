# Deployment Guide for Scaled Cloud Run Pipeline

This guide details how to deploy the Swiss Auditor pipeline to Google Cloud Run with Pub/Sub for parallel processing.

## Prerequisites
- Google Cloud Project with Billing enabled.
- `gcloud` CLI installed and authenticated.
- APIs enabled: `run.googleapis.com`, `pubsub.googleapis.com`, `artifactregistry.googleapis.com`.

## 1. Environment Setup
Set your variables:
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export BUCKET_NAME="your-bucket-name"
export TOPIC_NAME="swiss-auditor-jobs"
export SERVICE_NAME="swiss-auditor-worker"
export IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
```

## 2. Pub/Sub Setup
Create the topic that will hold the queue of jobs:
```bash
gcloud pubsub topics create $TOPIC_NAME
```

## 3. Worker Service Deployment

We use **Cloud Build** to automate the build and deployment process defined in `cloudbuild.yaml`.

### Deploy using Cloud Build
This command builds the image, pushes it to GCR, and executes the `gcloud run deploy` command with the configured best practices (concurrency, memory, timeout).

```bash
gcloud builds submit --config cloudbuild.yaml . --gcs-log-dir=gs://liquidacionesraw/logs
```

Note: I had some memory errors on cloud run side so we need to increase the memory to 4Gi.

The `cloudbuild.yaml` file handles:
- **Build**: Creates the Docker image.
- **Push**: Uploads to `gcr.io/$PROJECT_ID/swiss-auditor-worker`.
- **Deploy**: Updates the Cloud Run service with:
  - Memory: `4Gi`
  - Timeout: `3600s`
  - Max Instances: `20`
  - Concurrency: `1`
  - No Allow Unauthenticated

## 4. Connect Pub/Sub to Cloud Run
Create a push subscription. This connects the queue to your worker.
First, create a service account for Pub/Sub invoker if needed, or use default.
```bash
# Create service account to represent the subscription identity
gcloud iam service-accounts create pubsub-invoker \
    --display-name "Pub/Sub Invoker"

# Give it permission to invoke the Run service
gcloud run services add-iam-policy-binding swiss-auditor-worker \
    --member=serviceAccount:pubsub-invoker@${PROJECT_ID}.iam.gserviceaccount.com \
    --role=roles/run.invoker \
    --region=southamerica-east1

# Create the subscription
gcloud pubsub subscriptions create swiss-auditor-jobs-sub \
    --topic swiss-auditor-jobs \
    --push-endpoint=$(gcloud run services describe swiss-auditor-worker --region southamerica-east1 --format 'value(status.url)') \
    --push-auth-service-account=pubsub-invoker@${PROJECT_ID}.iam.gserviceaccount.com \
    --ack-deadline 600
```
IMPORTANT: **Pub/Sub Push has a hard timeout of 10 minutes (600s).** It *cannot* be increased to 1200s for Push subscriptions.

### Handling Long-Running Processing (> 10 minutes)
Since processing large PDFs with Gemini agents can easily exceed the 10-minute Pub/Sub Push timeout, the Cloud Run worker is designed to process tasks asynchronously:
1. **Immediate Acknowledgment**: The `/` endpoint immediately returns a `200 OK` to Pub/Sub upon receiving the valid payload. This prevents Pub/Sub from timing out and redelivering the message.
2. **Background Threading**: The actual task execution (GCS download, AI pipeline, AlloyDB ingestion) is spawned in a background thread.
3. **CPU Allocation**: The Cloud Run service is deployed with `--no-cpu-throttling` (`cpu: always`) to ensure the background thread completes successfully after the HTTP response is sent.

## 5. Automatic GCS Trigger
Configure Pub/Sub to listen to GCS `OBJECT_FINALIZE` events.

1.  **Grant permissions** to GCS service agent to publish to Pub/Sub:
    ```bash
    # Find your GCS service account - OK
    gsutil kms serviceaccount -p $PROJECT_ID
    # output: service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com

    # Grant role
    gcloud pubsub topics add-iam-policy-binding swiss-auditor-jobs \
      --member="serviceAccount:service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com" \
      --role="roles/pubsub.publisher"
    ```

2.  **Create Notification**:
    ```bash
    gsutil notification create -t swiss-auditor-jobs -f json -e OBJECT_FINALIZE gs://liquidacionesraw
    ```
    
    *Optional: List notifications to verify it was created successfully:*
    ```bash
    gsutil notification list gs://liquidacionesraw
    ```

**IMPORTANT**: GCS fires an event for *every* uploaded file. To avoid triggering the pipeline 10 times for 10 files (and failing because files are missing), we have configured the worker to **ONLY** start when it sees a file ending in `.trigger`.

**Workflow:**
1.  Upload your folder with all PDFs: `gsutil cp -r data/folder gs://$BUCKET_NAME/data/`
2.  **Triger the process** by uploading an empty marker file:
    ```bash
    touch START.trigger
    gsutil cp START.trigger gs://$BUCKET_NAME/data/folder/START.trigger
    ```
    (Or just upload any file ending in `.trigger` to that folder).
