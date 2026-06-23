# AlloyDB Credentials & Secret Manager Setup

This guide explains how to securely manage your AlloyDB credentials using Google Secret Manager and inject them into your Cloud Run service.

## 1. Where to find AlloyDB Credentials

1.  **Go to Google Cloud Console** > **AlloyDB** > **Clusters**.
2.  Click on your **Cluster ID**.
3.  **Host (IP Address)**:
    *   Look for the **Primary Instance** in the list.
    *   Copy the **Private IP** address from the PSC.
4.  **Database Name**:
    *   Default is `postgres`.
    *   Or check the "Databases" tab to see custom databases.
5.  **User & Password**:
    *   **User**: Default is `postgres`. You can create new users in the "Users" tab.
    *   **Password**: This was set when you created the cluster. If you forgot it, click the "Primary Instance" and then **Edit** > **Change Password**.

---

## 2. Create Secrets in Secret Manager

We will create secrets for the sensitive values: `DB_PASSWORD`, `DB_USER`, `DB_HOST`, `DB_NAME`.

Run these commands in your terminal:

```bash
# 1. DB Password
gcloud secrets create db-password --replication-policy="automatic"
echo -n "YOUR_ACTUAL_PASSWORD" | gcloud secrets versions add db-password --data-file=-

# 2. DB Host (IP)
gcloud secrets create db-host --replication-policy="automatic"
echo -n "10.x.x.x" | gcloud secrets versions add db-host --data-file=-

# 3. DB User
gcloud secrets create db-user --replication-policy="automatic"
echo -n "postgres" | gcloud secrets versions add db-user --data-file=-

# 4. DB Name
gcloud secrets create db-name --replication-policy="automatic"
echo -n "postgres" | gcloud secrets versions add db-name --data-file=-
```

---

## 3. Grant Access to Cloud Run

Your Cloud Run service account needs permission to read these secrets.

1.  **Find your Cloud Run Service Account**:
    By default, it is the Compute Engine default service account: `PROJECT_NUMBER-compute@developer.gserviceaccount.com`.

    Note: Check this by running `gcloud run services describe swiss-auditor-worker --region us-central1` and looking for `serviceAccountName`.

2.  **Grant Permission**:
    ```bash
    export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    
    # Grant Secret Accessor role
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
    ```
---

## 4. Verify

1.  Deploy the changes:
    ```bash
    gcloud builds submit --config cloudbuild.yaml .
    ```
2.  Your `run_batch_gcs.py` will pick up `os.environ.get("DB_PASSWORD")`.
