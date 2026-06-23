# Comprehensive Post-Deployment Architecture Validation Checklist

This checklist helps you verify that the entire Swiss Auditor infrastructure consists of networking, databases, secrets, compute, and eventing services are properly deployed and configured. You can validate these settings through the Google Cloud Console (UI) or using the `gcloud`/`gsutil` CLI commands.

## 1. Networking & VPC
**Goal**: Ensure VPC and Subnets are configured for private internal communication (for AlloyDB and Cloud Run Direct VPC Egress).

* **UI**: 
  1. Go to **VPC network > VPC networks**.
  2. Verify your expected VPC network exists (e.g., `vpc-nonprod-shared` or `shared-vpc-argolis`).
  3. Go to **Subnets** and verify your application subnet exists (e.g., `subnet-non-prod-1` or `subnet-apps-01`) with Private Google Access enabled.
* **CLI**:
  ```bash
  gcloud compute networks list
  gcloud compute networks subnets list --network=[YOUR_VPC_NAME]
  ```

---

## 2. Shared Services & Secrets
**Goal**: Verify Artifact Registry repository and Secret Manager secrets exist.

* **UI**:
  1. Go to **Artifact Registry > Repositories** and verify the Docker repository `cloudrun-images` exists.
  2. Go to **Security > Secret Manager** and verify the following secrets exist: `db-password`, `db-host`, `db-user`, `db-name`.
* **CLI**:
  ```bash
  gcloud artifacts repositories list
  gcloud secrets list
  ```

---

## 3. Database (AlloyDB)
**Goal**: Confirm AlloyDB cluster and instances are running.

* **UI**:
  1. Go to **Databases > AlloyDB**.
  2. Verify your cluster is in a `READY` state.
  3. Verify the primary instance is active.
* **CLI**:
  ```bash
  gcloud alloydb clusters list --region=[YOUR_REGION]
  gcloud alloydb instances list --cluster=[YOUR_CLUSTER_NAME] --region=[YOUR_REGION]
  ```

---

## 4. Google Cloud Storage
**Goal**: Verify input/output buckets are created.

* **UI**:
  1. Go to **Cloud Storage > Buckets**.
  2. Verify your pipeline bucket (e.g., `liquidacionesraw`) exists.
* **CLI**:
  ```bash
  gsutil ls
  ```

---

## 5. Service Accounts & IAM
**Goal**: Ensure correct permissions are granted to various service accounts to allow cross-service communication.

### A. Compute Engine Default Service Account (Worker Identity)
* **UI**: Go to **IAM & Admin > IAM**, search for the compute engine SA (e.g., `[PROJECT_NUMBER]-compute@developer.gserviceaccount.com`).
* **Validation**: It must have the following roles: 
  * **Storage Object Admin**
  * **Vertex AI User**
  * **Secret Manager Secret Accessor**

### B. Pub/Sub Service Agent / Invoker (Trigger Identity)
* **UI**: 
  1. Go to **Cloud Run**.
  2. Click on the `swiss-auditor-worker` service.
  3. Go to the **Security** tab.
  4. Look at the Permissions list.
* **Validation**: Verify that the `pubsub-invoker` service account (or the Pub/Sub Service Agent) has the **Cloud Run Invoker** (`roles/run.invoker`) role.

### C. Cloud Storage Service Agent (Event Publisher)
* **UI**: 
  1. Go to **Pub/Sub > Topics**.
  2. Click on the `swiss-auditor-jobs` topic.
  3. Open the **Permissions** or **Info Panel** on the right side.
* **Validation**: The GCS service agent (formatted as `service-[PROJECT_NUMBER]@gs-project-accounts.iam.gserviceaccount.com`) must have the **Pub/Sub Publisher** (`roles/pubsub.publisher`) role on this topic.

---

## 6. Cloud Run (Worker Service)
**Goal**: Confirm the application is deployed and correctly configured.

* **UI**:
  1. Go to **Cloud Run**.
  2. Click `swiss-auditor-worker`.
  3. **Revisions**: Ensure the latest revision is deployed successfully and receiving 100% of traffic.
  4. **Variables & Secrets**: Check the configurations (Edit & Deploy New Revision > Variables & Secrets) to see if `GOOGLE_GENAI_USE_VERTEXAI` is `true`, and secrets (`DB_PASSWORD`, `DB_HOST`, etc.) are mapped correctly.
  5. **Networking**: Check the Networking tab to ensure **Direct VPC Egress** is selected and pointing to the proper VPC/subnet.

---

## 7. Pub/Sub & Events
**Goal**: Confirm messaging infrastructure routes events correctly from GCS down to Cloud Run.

### A. Topic
* **UI**: Go to **Pub/Sub > Topics**. Verify `swiss-auditor-jobs` exists.

### B. Subscription
* **UI**: 
  1. Go to **Pub/Sub > Subscriptions**. 
  2. Click `swiss-auditor-jobs-sub`.
* **Validation**: 
  1. **Delivery type** is set to **Push**.
  2. **Endpoint URL** matches the URL of the `swiss-auditor-worker` Cloud Run service.
  3. Under push details, the **Service Account** matches the Pub/Sub Invoker.

### C. GCS Notification
* **UI**: 
  *(GCS bucket notifications configured this way are not prominent in the UI. We recommend using the CLI below to verify).*
* **CLI**:
  ```bash
  gsutil notification list gs://liquidacionesraw
  ```
  *(Expected: Output should look similar to this:)*
  ```text
  projects/_/buckets/liquidacionesraw/notificationConfigs/...
        Cloud Pub/Sub topic: projects/[YOUR_PROJECT_ID]/topics/swiss-auditor-jobs
        Filters:
                Event Types: OBJECT_FINALIZE
  ```

---

## 8. Required Permissions for Validation
**Goal**: Ensure your own user account has the required IAM roles to run the validation commands and view the resources in the UI.

To fully validate this architecture, your Google Cloud identity (User or Service Account) must have the following roles (or equivalent custom roles) granted at the Project level:

* **`roles/compute.networkViewer`**: To view VPC networks and subnets.
* **`roles/artifactregistry.reader`**: To view the Artifact Registry repositories.
* **`roles/secretmanager.viewer`**: To list secrets in Secret Manager.
* **`roles/alloydb.viewer`**: To view AlloyDB clusters and instances.
* **`roles/storage.admin`** or **`roles/storage.objectViewer`**: To list buckets and view GCS notifications.
* **`roles/iam.serviceAccountViewer`**: To view Service Accounts and their IAM policies.
* **`roles/run.viewer`**: To view Cloud Run services, their revisions, and their security settings.
* **`roles/pubsub.viewer`**: To view Pub/Sub topics, subscriptions, and their configurations.

### How to Check Your Assigned Roles
You can fetch the roles assigned to your currently authenticated `gcloud` user account by running:
```bash
# Get your currently logged-in email
USER_EMAIL=$(gcloud config get-value account)

# List the IAM policies bindings where you are a member
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:${USER_EMAIL}" \
    --format="value(bindings.role)"
```

---

## 9. Required Permissions to Execute the Setup Commands
**Goal**: Ensure you have the permissions necessary to actually *run* the commands you shared (creating service accounts, subscriptions, and modifying IAM policies).

The Viewer roles listed in Step 8 only allow you to read the configuration. If you need to re-run your setup commands to fix a missing piece of infrastructure, you will need elevated **Admin/Creator** roles:

* **`roles/iam.serviceAccountCreator`**: To create the `pubsub-invoker` service account.
* **`roles/run.admin`**: To add the IAM policy binding to the Cloud Run service (`run services add-iam-policy-binding`).
* **`roles/pubsub.editor`** (or `roles/pubsub.admin`): To create the Pub/Sub subscription and add the IAM policy binding to the topic.
* **`roles/storage.admin`**: To create the GCS bucket notification (`gsutil notification create`).

---

## 10. How to Test the End-to-End Flow
**Goal**: Verify that dropping files into the GCS bucket actually triggers the pipeline successfully.

To test this, you will need the ability to write to the bucket (`roles/storage.objectUser` or `roles/storage.objectAdmin`), which allows you to upload a file and trigger the notification.

1. **Upload a Test Document**:
   Create a test folder and upload a PDF.
   ```bash
   gsutil cp test_invoice.pdf gs://liquidacionesraw/test_investigation_001/invoice.pdf
   ```

2. **Upload the Trigger File**:
   As per the architecture design, the worker strictly filters for a special marker file named `.trigger` to ensure all documents are present before processing begins.
   ```bash
   touch .trigger
   gsutil cp .trigger gs://liquidacionesraw/test_investigation_001/.trigger
   ```
   *(Uploading this file fires the `OBJECT_FINALIZE` event that triggers your Pub/Sub -> Cloud Run flow).*

3. **Verify the Execution**:
   * Open the **Cloud Run** console UI, click on `swiss-auditor-worker`.
   * Go to the **Logs** tab and verify that the service received the push request and began processing the `test_investigation_001` folder without errors.
   * Check the **AlloyDB** database or the GCS bucket (`gs://liquidacionesraw/test_investigation_001/`) to see if the resulting `.json` audit files were created.
