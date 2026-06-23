# DESIGN_SPEC.md - Gemini Enterprise Agent

## Overview
The `gemini_enterprise` agent is designed to assist auditors in investigating cases by providing access to case documents and structured metrics.
It takes an `investigation_id` as context (which corresponds to a GCS bucket name) and enables the user to:
1.  **Analyze Documents**: Read and query `.pdf` and `.json` files stored in the investigation's GCS bucket.
2.  **Query Metrics**: Retrieve and aggregate data from AlloyDB regarding investigations, billing items, and audit discrepancies.

## Example Use Cases
*   **User**: "What is the total estimated overbilling for investigation 1619_73677_011?"
    **Agent**: Queries AlloyDB table `investigations` for `id='1619_73677_011'` and returns the `estimated_total_overbilling`.
*   **User**: "List the discrepancies found in the documents for this investigation."
    **Agent**: Queries AlloyDB table `audit_discrepancies` or reads the audit JSON from GCS and lists them.
*   **User**: "Summarize the clinical history found in the PDF files."
    **Agent**: Lists files in GCS, identifies clinical PDFs, extracts text, and summarizes.

## Tools Required

### 1. `list_gcs_files`
*   **Purpose**: List all files in the GCS bucket for the investigation.
*   **Arguments**: `investigation_id: str`
*   **Returns**: List of file paths.

### 2. `read_gcs_file`
*   **Purpose**: Read the content of a specific file (PDF or JSON) from GCS.
*   **Arguments**: `investigation_id: str`, `file_name: str`
*   **Returns**: Text content or JSON dictionary. For PDFs, extracts text.

### 3. `query_alloydb`
*   **Purpose**: Execute a SELECT query on AlloyDB to retrieve metrics.
*   **Arguments**: `query: str`
*   **Returns**: Query results as a list of dictionaries.
*   **Safety**: MUST only execute `SELECT` statements.

## Constraints & Safety Rules
*   **READ-ONLY**: The agent must NOT modify any data in GCS or AlloyDB.
*   **Scope Range**: The agent must only access the GCS bucket matching the `investigation_id` provided or referenced.
*   **SQL Injection**: The `query_alloydb` tool should ensure only read-only queries are executed.

## Success Criteria
*   Agent can correctly identify files in GCS based on ID.
*   Agent can extract text from PDF files.
*   Agent can connect to AlloyDB and retrieve correct values from `investigations` and `billing_items` tables.

## Edge Cases to Handle
*   GCS bucket does not exist or is empty.
*   PDF file is encrypted or has no text.
*   AlloyDB connection fails.
*   No records found for the given `investigation_id`.
