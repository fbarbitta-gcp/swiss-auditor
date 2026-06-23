# Swiss Auditor Retry Job

This is a standalone Cloud Run Job designed to periodically scan the `liquidacionesraw` GCS bucket for processing failures or missing triggers in the Swiss Auditor pipeline.

Because the main `swiss-auditor-worker` service is specialized for handling heavy Generative AI tasks asynchronously via Eventarc, bundling a periodic bucket scanner inside it was considered an anti-pattern. This job runs entirely independently, spins up when triggered by Cloud Scheduler, creates the necessary `.trigger` files, and immediately shuts down to save costs and resources.

## What It Does
1. Iterates over all files in the target bucket.
2. Identifies any old `.trigger` files that were not processed (overwrites them to force a retry).
3. Identifies any old PDF invoice folders that never had a trigger file uploaded (creates a new `autoscan.trigger`).
4. Ignores new files to prevent race conditions with incoming user uploads.

## Core Retry Logic

The retry job ensures eventual consistency by scanning GCS folders that haven't been successfully processed. The condition for skipping or retriggering is based on the following criteria:

1. **Age Threshold (Cooldown):** The job dynamically calculates the *newest modified file* in each directory. If the newest file is younger than the `AGE_HOURS` threshold (default 2 hours), the directory is explicitly skipped. This mechanism acts as a cooldown to avoid retriggering a folder while it is actively being uploaded by users or actively being processed by the worker.
2. **Success Verification:** If a folder already contains any `.json` files (e.g., `_billing_result.json`), it indicates that the pipeline completed successfully in the past but perhaps the directory was not moved. The job ignores these folders indefinitely.
3. **Failed Pipelines:** For folders that possess a `.trigger` file but never yielded JSON results (and surpassed the 2-hour cooldown), it's assumed the pipeline crashed during execution or timed out. In this scenario, the script overwrites the existing `.trigger` file, generating a fresh `google.storage.object.finalize` Eventarc event to restart the async worker.
4. **Missing Triggers:** For folders containing `.pdf` files but lacking any `.trigger` files, the job generates a new `autoscan.trigger`. This guarantees that eventually all valid folders are sent to the pipeline even if human operators forgot to upload a trigger piece.

## Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `BUCKET_NAME` | The Google Cloud Storage bucket to scan for unprocessed jobs. | `liquidacionesraw` |
| `AGE_HOURS` | Files modified more recently than this threshold are ignored. | `2.0` |

## Deployment

This job is deployed natively through Terraform (`shared-vpc-iac/modules/worker_application/cloudrun_job.tf`). However, the container image needs to be built and pushed to Artifact Registry/Container Registry in order for Terraform to successfully spin it up.

### Using Cloud Build

You can build and update the image using the provided `cloudbuild.yaml` file natively on Google Cloud.

```bash
gcloud builds submit --config cloudbuild.yaml .
```

*Note: The `cloudbuild.yaml` executes `gcloud run jobs update swiss-auditor-worker-retry`, meaning you must first provision the Job placeholder via Terraform before your first Cloud Build pipeline runs.*
