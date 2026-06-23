# AlloyDB Setup Guide (PSC / Private Service Connect)

This guide provides step-by-step instructions to create an AlloyDB cluster using **Private Service Connect (PSC)**. This method is often preferred over VPC Peering as it avoids IP conflicts and provides granular access control.

## Prerequisites
- Google Cloud Project with Billing enabled.
- `gcloud` CLI installed and authenticated.

## Step 1: Enable APIs
Enable the necessary APIs for AlloyDB and networking.
```bash
gcloud services enable \
    alloydb.googleapis.com \
    compute.googleapis.com
```

## Step 2: Network Configuration (PSC)
Instead of VPC Peering, we will use PSC interactions.

1.  **Create your VPC and Subnet** (if you don't have one):
    *AlloyDB instances sit in Google's managed network, and you "reach" them via a PSC endpoint in your VPC.*


    Note: We can setup this from the console too.

    ```bash
    gcloud compute networks create my-network --subnet-mode=custom
    gcloud compute networks subnets create my-subnet \
      --network=my-network \
      --range=10.0.0.0/24 \
      --region=us-central1
    ```

## Step 3: Create Cluster (PSC Enabled)
When creating the cluster, you must specify that it processes PSC requests.

**Using the Console (Recommended for PSC setup):**
1.  Create Cluster.
2.  Networking: Choose **"Private Service Connect (PSC)"**.
3.  Finish creation.
4.  Copy the **Service Attachment URI** from the Primary Instance details page.

## Step 4: Create PCS Endpoint
To access the database from the VPC (and Cloud Run), you need an endpoint IP.

1.  **Create a Forwarding Rule (PSC Endpoint)** pointing to the AlloyDB Service Attachment.
    ```bash
    gcloud compute addresses create alloydb-psc-ip \
       --region=$REGION --subnet=my-subnet --internal

    gcloud compute forwarding-rules create alloydb-psc-endpoint \
       --region=$REGION \
       --network=my-network \
       --address=alloydb-psc-ip \
       --target-service-attachment=projects/PROJECT/regions/REGION/serviceAttachments/ALLOYDB_SERVICE_ATTACHMENT
    ```

Now, the IP address of `alloydb-psc-ip` is your **DB_HOST**.

## Step 5: Connect & Create Schema
You connect using standard PostgreSQL tools to the PSC Endpoint IP.

### From Cloud Run (Direct VPC Egress)
1.  Configure Cloud Run to use **Direct VPC Egress** (`--network=my-network --subnet=my-subnet`).
2.  Set `DB_HOST` to the **PSC Endpoint IP** (e.g., `10.0.0.5`).
3.  Using standard `psycopg2`.
