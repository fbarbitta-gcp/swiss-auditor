# Required IAM Permissions for Deployment Workflow

This document details the minimal set of Google Cloud IAM roles a user or service account must have to successfully execute the commands listed in `docs/DEPLOY_WORKFLOW.md`.

To run the complete end-to-end deployment, the caller must be granted the following roles at the Project level:

## 1. Pub/Sub Management
To create topics, subscriptions, and modify IAM policies on topics.
* **`roles/pubsub.admin`** (Pub/Sub Admin)
  * *Used for:* 
    * `gcloud pubsub topics create`
    * `gcloud pubsub subscriptions create`
    * `gcloud pubsub topics add-iam-policy-binding`

## 2. Cloud Build & Artifact Registry
To trigger the automated build process which pushes container images and deploys to Cloud Run.
* **`roles/cloudbuild.builds.editor`** (Cloud Build Editor)
  * *Used for:*
    * `gcloud builds submit --config cloudbuild.yaml`
*(Note: The Cloud Build service account itself also needs permissions like `roles/run.admin`, `roles/artifactregistry.writer`, and `roles/iam.serviceAccountUser` to deploy the app, but the user running the command primarily needs the Builder role).*

## 3. Cloud Run Management
To modify the IAM policy of the deployed worker service to allow Pub/Sub to invoke it.
* **`roles/run.admin`** (Cloud Run Admin)
  * *Used for:*
    * `gcloud run services add-iam-policy-binding`

## 4. Service Account Management
To create the dedicated invoker service account and attach it to the Pub/Sub subscription.
* **`roles/iam.serviceAccountCreator`** (Service Account Creator)
  * *Used for:*
    * `gcloud iam service-accounts create`
* **`roles/iam.serviceAccountUser`** (Service Account User)
  * *Used for:*
    * Assigning the SA to the subscription via `--push-auth-service-account`

## 5. Google Cloud Storage & Notifications
To configure the bucket to send events to Pub/Sub when new files arrive, and to retrieve the GCS service agent identity.
* **`roles/storage.admin`** (Storage Admin)
  * *Used for:*
    * `gsutil kms serviceaccount`
    * `gsutil notification create`
    * Writing logs via `--gcs-log-dir=gs://...` during the build step.

---

## Summary of Roles to Request
If you need to request access from your GCP Organization Administrator, provide them this exact list for your project (`<YOUR_PROJECT_ID>`):

1. `roles/pubsub.admin`
2. `roles/cloudbuild.builds.editor`
3. `roles/run.admin`
4. `roles/iam.serviceAccountCreator`
5. `roles/iam.serviceAccountUser`
6. `roles/storage.admin`

## Assignment Commands
If you have a Project IAM Admin (`roles/resourcemanager.projectIamAdmin`) or Project Owner role, you can run the following `curl` command to add all the required permissions to your account (`<YOUR_USER_EMAIL>`) at once. 

*(Note: This uses the `setIamPolicy` API, which overwrites the existing policy. To avoid overwriting other users' permissions, it's generally safer to use `gcloud projects add-iam-policy-binding` in a loop, but here is the REST API approach for adding bindings if needed).*

Since directly updating the entire IAM policy via `curl` requires downloading the current policy, merging it, and uploading it back (to avoid deleting everyone else's access), the easiest and safest one-liner using Google's REST API is actually an inline script that does exactly this via `curl` and `jq`:

```bash
curl -s -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "Content-Type: application/json" \
     "https://cloudresourcemanager.googleapis.com/v1/projects/<YOUR_PROJECT_ID>:getIamPolicy" | \
jq '.bindings += [
  {"role": "roles/pubsub.admin", "members": ["user:<YOUR_USER_EMAIL>"]},
  {"role": "roles/cloudbuild.builds.editor", "members": ["user:<YOUR_USER_EMAIL>"]},
  {"role": "roles/run.admin", "members": ["user:<YOUR_USER_EMAIL>"]},
  {"role": "roles/iam.serviceAccountCreator", "members": ["user:<YOUR_USER_EMAIL>"]},
  {"role": "roles/iam.serviceAccountUser", "members": ["user:<YOUR_USER_EMAIL>"]},
  {"role": "roles/storage.admin", "members": ["user:<YOUR_USER_EMAIL>"]}
]' | \
curl -s -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "Content-Type: application/json" \
     -d @- \
     "https://cloudresourcemanager.googleapis.com/v1/projects/<YOUR_PROJECT_ID>:setIamPolicy"
```
