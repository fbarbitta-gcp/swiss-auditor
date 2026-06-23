# Swiss Auditor - Repository Documentation

## 1. Overview
The **Swiss Auditor** project is an AI-powered system designed to automate the auditing of medical insurance claims. It leverages a **Multi-Agent System (MAS)** built on the Google Agent Development Kit (ADK) and Gemini 2.5 Flash to process unstructured documents (invoices, medical records), extract structured data, verify clinical evidence, and identify economic discrepancies (audits).

The system is deployed on **Google Cloud Run** for compute, uses **Google Cloud Storage (GCS)** for document and result persistence, and **AlloyDB (PostgreSQL)** for structured queryable data.

> **[See Deployment Guide](deployment_guide.md)** for detailed permissions, secrets, and infrastructure setup.

## 2. Step-by-Step Architecture

### High-Level Data Flow
1.  **Ingestion**: Documents are uploaded to a specific GCS bucket folder structure (e.g., `data/investigation_id/`).
2.  **Dispatch**: A dispatcher script scans for new folders and sends tasks to a Pub/Sub topic.
3.  **Orchestration**: A Cloud Run worker receives the message, downloads documents, and initiates the AI pipeline.
4.  **AI Pipeline**:
    *   **Agent 1 (Billing)**: Extracts line items from invoices.
    *   **Agent 2 (Verification)**: verification of medical services against clinical records.
    *   **Agent 3 (Audit)**: Cross-references billing vs. verification to find discrepancies.
5.  **Persistence**: JSON results are saved to GCS, and structured records are upserted into AlloyDB.

### Detailed Component Interaction

#### A. Trigger & Dispatch
*   **Trigger**:
    *   **Batch**: `dispatch_jobs.py` manually lists folders in GCS and publishes JSON payloads to the `projects/{id}/topics/{topic}` Pub/Sub topic.
    *   **Event-Driven**: `worker_service.py` listens for GCS Object Finalize events (via Pub/Sub or Eventarc). It strictly filters for a special marker file (`.trigger`) to ensure all documents are present before processing begins.
*   **Payload**: `{"bucket": "...", "folder_prefix": "..."}`

#### B. Worker Service (`worker_service.py`)
*   **Role**: Entry point for the Cloud Run service.
*   **Mechanism**:
    *   Exposes a Flask endpoint `/` receiving POST requests from Pub/Sub.
    *   **Async Processing**: To prevent HTTP timeouts (Cloud Run requests have a limit), it immediately acknowledges the message (HTTP 200) and spawns a background thread using `threading.Thread`.
    *   **Resiliency**: Uses `tenacity` retry logic for the background worker to handle transient failures.

#### C. Core Orchestrator (`run_batch_gcs.py`)
*   **Role**: Manages the lifecycle of a single investigation processing task.
*   **Steps**:
    1.  **Idempotency Check**: Checks if `{folder_name}_economic_audit_result.json` already exists in GCS. If so, skips processing.
    2.  **Document Classification**:
        *   Lists all PDFs in the folder.
        *   Identifies the **Invoice** based on keywords (`rendicion`, `factura`, `factmed`) or heuristic (single file = both invoice and history).
        *   Treats all other PDFs as **Clinical History**.
    3.  **Download**: Fetches files to a local temporary directory (e.g., `/tmp/swiss_auditor_worker`).
    4.  **Pipeline Execution**: Calls `agents.pipeline.run_pipeline`.
    5.  **Upload Results**: Uploads the generated JSON output files back to the GCS folder.
    6.  **DB Ingestion**: Calls `ingest_results` to parse the JSONs and write to Postgres (AlloyDB).

#### D. AI Agent Pipeline (`agents/pipeline.py`)
This is the "Brain" of the system, executed sequentially using `google.adk`.

1.  **Billing Extraction Agent**:
    *   **Input**: Invoice PDF.
    *   **Action**: Extracts `afiliado` details, medications, amounts, and costs.
    *   **Logic**: Splits large PDFs (>200 pages) into chunks to manage context.
    *   **Output**: `billing_result.json`.

2.  **Targeted Verification Agent**:
    *   **Input**: Clinical History PDFs + `billing_extraction_result` (injected into session state).
    *   **Action**: Verifies if billed items appear in the clinical records (prescribed/administered).
    *   **Output**: `targeted_verification_result.json`.

3.  **Economic Audit Agent**:
    *   **Input**: Invoice PDF + Billing Result + Verification Result.
    *   **Action**: Cross-references verified data against the invoice to determine status (`MATCH`, `OVERBILLED`, `NOT_PRESCRIBED`, `NOT_ADMINISTERED`).
    *   **Output**: `economic_audit_result.json`.

#### E. Data Layer (`schema.sql` & Ingestion)
Records are stored in a relational schema for analytics:
*   **`investigations`**: One record per case. Stores high-level metrics (total overbilling, matches). Uses `ON CONFLICT` for updates.
*   **`billing_items`**: Detailed line items from the invoice.
*   **`audit_discrepancies`**: Specific findings (e.g., "Drug X billed but not found in history").
*   **Ingestion Logic**: Performs a `DELETE` of items for the specific investigation ID before `INSERT` to ensure clean re-runs without duplicates.

## 3. Code Structure

```text
/
├── agents/                     # AI Logic
│   ├── billing_agent.py        # Agent definition
│   ├── economic_audit_agent.py # Agent definition
│   ├── verification_agent.py   # Agent definition
│   ├── pipeline.py             # Orchestrates the sequential agent execution
│   └── schemas.py              # Pydantic models for structured output
├── utils/                      # Shared Utilities
│   └── gcs_utils.py            # GCS Helper class (list, download, upload)
├── worker_service.py           # Cloud Run Entrypoint (Flask + Threading)
├── dispatch_jobs.py            # Script to trigger batch jobs via Pub/Sub
├── run_batch_gcs.py            # Component logic for processing a single folder
├── schema.sql                  # Database DDL
├── Dockerfile                  # Container definition
├── cloudbuild.yaml             # CI/CD pipeline
└── requirements.txt            # Python dependencies
```

## 4. Design Decisions

1.  **Isolated Sessions vs. Continuous Chat**: 
    *   The pipeline creates a *new* `InMemorySessionService` for each step. This ensures clean context windows and prevents "hallucination drift" where an agent might be confused by previous turn history irrelevant to its specific sub-task.
    *   State is explicitly passed: `billing_result` is retrieved from Step 1 and manually injected into the `initial_state` of Step 2.

2.  **Background Processing in Cloud Run**:
    *   Instead of using Cloud Tasks to trigger a long-running HTTP request (which has a timeout hard limit), the service accepts the Pub/Sub message and processes it in a background thread.
    *   **Trade-off**: Requires CPU allocation to be enabled even after the response is sent (`cpu: always` in Cloud Run gen2) to avoid CPU throttling during background work.

3.  **Chunking Strategy**:
    *   PDFs > 200 pages are split (in `pipeline.py`).
    *   Reason: While Gemini 1.5/2.5 has a massive context window (1M+ tokens), sending extremely large files can still incur latency penalties or hitting payload size limits in client libraries.

4.  **Database Idempotency**:
    *   The ingestion logic (`run_batch_gcs.py`) specifically deletes child records (`billing_items`, `audit_discrepancies`) for a given `investigation_id` before inserting. This allows the pipeline to be re-run on the same folder without duplicating data.

## 5. Improvements & Recommendations

### Architecture & Reliability
1.  **Replace Threading with Cloud Run Jobs**:
    *   **Current**: `worker_service.py` uses background threads. If the container crashes or scales down, work is lost.
    *   **Recommendation**: Use **Cloud Run Jobs** for the actual processing. The Pub/Sub trigger could launch a Job execution. This provides better observability, timeout management (up to 24h), and independent scaling.

2.  **Robust Trigger Mechanism**:
    *   **Current**: Relies on a `.trigger` file or manual dispatch.
    *   **Recommendation**: Implement a formal "Manifest" approach where a JSON file describes the case `metadata.json` (patient ID, file list). Processing only starts when this manifest is finalized.

3.  **Queue Management**:
    *   `dispatch_jobs.py` dumps everything to Pub/Sub. For massive backfills, this might overwhelm the DB connection pool.
    *   **Recommendation**: Implement flow control or use Cloud Tasks for rate-limiting the dispatch to the workers.

### Code & Logic
4.  **PDF Chunking Intelligence**:
    *   **Current**: Arbitrary 200-page split.
    *   **Recommendation**: Split specific to the document type (e.g., split invoices by "Concepto" sections, or clinical history by Date/Admission). This prevents splitting a logical record in half.

5.  **Hardcoded Paths**:
    *   **Current**: Uses `/tmp/swiss_auditor_worker`.
    *   **Recommendation**: Use `tempfile.TemporaryDirectory()` context managers to ensure cleanup even on crashes and avoid collisions if multiple threads ran on one instance (though uncommon in this design).

6.  **Observability**:
    *   **Current**: `logging.info`.
    *   **Recommendation**: Integrate **Structured Logging** (JSON format) with `trace_id` correlation to link the Pub/Sub message -> Worker -> Pipeline -> AlloyDB records in Cloud Logging.

### AI / Agents
7.  **Dynamic Planner**:
    *   **Current**: `BuiltInPlanner(thinking_budget=0)`.
    *   **Recommendation**: For complex cases (e.g., fuzzy matching names), enabling a small "thinking budget" for the `verification_agent` might improve accuracy in matching drug names (e.g., "Paracetamol" vs "Acetaminophen").
