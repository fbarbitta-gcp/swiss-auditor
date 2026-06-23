# PDF Processing Scenarios

The `run_batch_gcs.py` script automatically identifies **Invoice** and **Clinical History** files from a folder based on the count of PDF files and their filenames.

## Scenario 1: Multiple Files (Standard)

When a folder contains multiple PDF files, the system uses keyword matching to identify the invoice.

-   **Invoice Identification:**
    -   Any file whose name contains (case-insensitive):
        -   `rendicion`
        -   `factura`
        -   `factmed`
    -   *Note: If multiple files match, the last one processed is used.*
-   **Clinical History Identification:**
    -   **All other PDF files** in the folder are treated as Clinical History.

## Scenario 2: Single File

When a folder contains exactly **one** PDF file.

-   **Behavior:**
    -   The single file is treated as **both** the **Invoice** AND the **Clinical History**.
    -   No keyword matching is performed.

## Fallback & Validation

-   **No Invoice Found (Multiple Files):** If multiple files exist but none contain the invoice keywords, the folder is **skipped** with a warning.
-   **No Clinical History Found:** If an invoice is found but no other files exist (and it's not Scenario 2), the folder is **skipped** (unless the invoice file itself is somehow also clinical history, which current logic for multiple files precludes).
