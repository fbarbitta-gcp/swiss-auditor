# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import asyncio
import logging
import traceback
import argparse
import json
import uuid
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values

from utils.gcs_utils import GCSClient
from agents.pipeline import run_pipeline

import contextvars

trace_id_var = contextvars.ContextVar('trace_id', default='N/A')

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True

# Configure logging
root_logger = logging.getLogger()
# Clear existing handlers to override any previous configuration (e.g. from imports)
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)

handler = logging.StreamHandler()
handler.addFilter(TraceIdFilter())
formatter = logging.Formatter('%(asctime)s - %(name)s - [%(trace_id)s] - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

def get_provider_rule(id_prestador: str) -> Optional[str]:
    """Queries AlloyDB for provider-specific keywords."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT keywords FROM prestadores WHERE id_prestador = %s", (id_prestador,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Error querying provider rule for {id_prestador}: {e}")
        if conn:
            conn.close()
        return None

def upsert_investigation_status(investigation_id: str, status: str, trace_id: Optional[str] = None):
    """Upserts the investigation status to the database."""
    conn = get_db_connection()
    if not conn:
        logger.error(f"Failed to upsert status for {investigation_id}: No DB connection.")
        return
    try:
        cur = conn.cursor()
        if trace_id:
            cur.execute("""
                INSERT INTO investigations (id, status, trace_id, processed_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, trace_id = EXCLUDED.trace_id, processed_at = EXCLUDED.processed_at;
            """, (investigation_id, status, trace_id))
        else:
            cur.execute("""
                INSERT INTO investigations (id, status, processed_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, processed_at = EXCLUDED.processed_at;
            """, (investigation_id, status))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Status '{status}' upserted for {investigation_id}")
    except Exception as e:
        logger.error(f"Error upserting status for {investigation_id}: {e}")
        if conn:
            conn.close()

def ingest_results(folder_name: str, local_temp_dir: str, trace_id: str):
    """Ingests the results from local JSON files into AlloyDB."""
    billing_file = os.path.join(local_temp_dir, f"{folder_name}_billing_result.json")
    audit_file = os.path.join(local_temp_dir, f"{folder_name}_economic_audit_result.json")
    
    if not os.path.exists(audit_file):
        logger.warning(f"Ingestion skipped for {folder_name}: Economic audit file not found.")
        return

    conn = get_db_connection()
    if not conn:
        logger.error(f"Ingestion skipped for {folder_name}: No DB connection.")
        return

    try:
        # Read Audit Result
        with open(audit_file, 'r') as f:
            audit_data = json.load(f)
            
        # Read Billing Result
        billing_data = {}
        if os.path.exists(billing_file):
            with open(billing_file, 'r') as f:
                billing_data = json.load(f)
        
        # Read Run Stats (Tokens and Models)
        stats_file = os.path.join(local_temp_dir, f"{folder_name}_run_stats.json")
        stats_data = {}
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                stats_data = json.load(f)
        
        usage_breakdown = stats_data.get("usage_breakdown", {})
        
        cur = conn.cursor()
        
        # 1. Upsert Investigation
        insert_investigation_sql = """
            INSERT INTO investigations (
                id, 
                processed_at, 
                status, 
                total_invoiced_items, 
                percent_match, 
                percent_overbilled, 
                percent_not_prescribed, 
                percent_not_administered, 
                estimated_total_overbilling,
                trace_id,
                token_usage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                processed_at = EXCLUDED.processed_at,
                status = EXCLUDED.status,
                total_invoiced_items = EXCLUDED.total_invoiced_items,
                percent_match = EXCLUDED.percent_match,
                percent_overbilled = EXCLUDED.percent_overbilled,
                percent_not_prescribed = EXCLUDED.percent_not_prescribed,
                percent_not_administered = EXCLUDED.percent_not_administered,
                estimated_total_overbilling = EXCLUDED.estimated_total_overbilling,
                trace_id = EXCLUDED.trace_id,
                token_usage = EXCLUDED.token_usage;
        """
        
        total_invoiced = audit_data.get("total_invoiced_items", 0)
        pct_match = audit_data.get("percent_match", 0.0)
        pct_over = audit_data.get("percent_overbilled", 0.0)
        pct_np = audit_data.get("percent_not_prescribed", 0.0)
        pct_na = audit_data.get("percent_not_administered", 0.0)
        est_over = audit_data.get("estimated_total_overbilling", 0.0)
        
        cur.execute(insert_investigation_sql, (
            folder_name,
            datetime.now(),
            'processed',
            total_invoiced,
            pct_match,
            pct_over,
            pct_np,
            pct_na,
            est_over,
            trace_id,
            json.dumps(usage_breakdown)
        ))
        
        # 2. Insert Billing Items
        cur.execute("DELETE FROM billing_items WHERE investigation_id = %s", (folder_name,))
        
        # Load Matched Results for column overrides if present
        matched_file = os.path.join(local_temp_dir, f"{folder_name}_matched_result.json")
        matches_by_key = {}
        if os.path.exists(matched_file):
            logger.info(f"Found matched results file for ingestion: {matched_file}")
            with open(matched_file, 'r') as f:
                m_data = json.load(f)
                for m_item in m_data.get("items", []):
                    key = (m_item.get("medication_name"), m_item.get("presentation"))
                    matches_by_key[key] = m_item

        if "afiliados" in billing_data:
            billing_items = []
            for afiliado in billing_data["afiliados"]:
                afiliado_name = afiliado.get("afiliado_name")
                afiliado_id = afiliado.get("afiliado_id")
                afiliado_doc = afiliado.get("afiliado_documento_identidad")
                
                for item in afiliado.get("medications", []):
                    key = (item.get("medication_name"), item.get("presentation"))
                    m_match = matches_by_key.get(key)
                    
                    # Preference rule
                    med_name = item.get("medication_name")
                    pres_name = item.get("presentation")
                    
                    if m_match:
                         med_name = m_match.get("matched_droga_principal") or med_name
                         pres_name = m_match.get("matched_presentacion") or pres_name

                    billing_items.append((
                        folder_name,
                        afiliado_id,
                        afiliado_name,
                        afiliado_doc,
                        med_name,
                        pres_name,
                        item.get("amount"),
                        item.get("cost_per_unit"),
                        item.get("total_cost"),
                        item.get("source_page")
                    ))

            
            if billing_items:
                execute_values(cur, """
                    INSERT INTO billing_items (
                        investigation_id, afiliado_id, afiliado_name, afiliado_documento_identidad,
                        medication_name, presentation, amount, cost_per_unit, total_cost, source_page
                    ) VALUES %s
                """, billing_items)

        # 3. Insert Audit Discrepancies
        cur.execute("DELETE FROM audit_discrepancies WHERE investigation_id = %s", (folder_name,))
        
        if "discrepancies" in audit_data:
            discrepancies = []
            for item in audit_data["discrepancies"]:
                pages = item.get("pages", [])
                discrepancies.append((
                    folder_name,
                    item.get("medication"),
                    item.get("prescribed"),
                    item.get("administered"),
                    item.get("administration_date"),
                    item.get("invoiced"),
                    item.get("discrepancy_type"),
                    item.get("unit_cost"),
                    item.get("estimated_overbilled_amount"),
                    item.get("observation"),
                    pages
                ))
            
            if discrepancies:
                execute_values(cur, """
                    INSERT INTO audit_discrepancies (
                        investigation_id, medication_name, prescribed_text, administered_text, administration_date, invoiced_text,
                        discrepancy_type, unit_cost, estimated_overbilled_amount, observation, source_pages
                    ) VALUES %s
                """, discrepancies)

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Successfully ingested {folder_name} into AlloyDB.")

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Error ingesting {folder_name}: {e}")
        raise e

async def process_gcs_folder(gcs_client: GCSClient, bucket_name: str, folder_prefix: str, local_temp_dir: str):
    """
    Processes a single folder from GCS.
    
    Args:
        gcs_client: Instance of GCSClient.
        bucket_name: GCS bucket name.
        folder_prefix: The prefix (virtual folder) in GCS (e.g., "data/25966_.../").
        local_temp_dir: Local path to store temporary files for processing.
    """
    folder_name = folder_prefix.rstrip('/').split('/')[-1]
    
    # Set log context to folder name initially
    trace_id_var.set(folder_name)
    
    # Check if output already exists in GCS
    expected_output_blob = f"{folder_prefix}{folder_name}_economic_audit_result.json"
    if gcs_client.file_exists(bucket_name, expected_output_blob):
        logger.info(f"Skipping {folder_name}: Output already exists in GCS.")
        return

    logger.info(f"Processing GCS folder: {folder_name}")
    
    # List all files in this GCS folder
    blobs = gcs_client.list_files(bucket_name, prefix=folder_prefix)
    pdf_blobs = [b for b in blobs if b.lower().endswith(".pdf")]
    
    invoice_blob = None
    clinical_blobs = []
    
    if len(pdf_blobs) == 1:
        invoice_blob = pdf_blobs[0]
        clinical_blobs = [pdf_blobs[0]]
        logger.info(f"Scenario 3 for {folder_name}: Single document detected. Using {os.path.basename(invoice_blob)} as both Invoice and Clinical History.")
    else:
        # Check provider rule first by looking at path segments (root folder)
        path_parts = folder_prefix.rstrip('/').split('/')
        id_prestador = None
        for part in path_parts:
            parts = part.split('_')
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                id_prestador = parts[1]
                logger.info(f"Using id_prestador {id_prestador} from path segment: {part} for subfolder {folder_name}")
                break
        keywords = get_provider_rule(id_prestador) if id_prestador else None
        
        if keywords:
            logger.info(f"Applying provider rule for {id_prestador} (Keywords: {keywords})")
            keyword_list = [k.strip().lower() for k in keywords.split(',') if k.strip()]
            for b in pdf_blobs:
                filename = os.path.basename(b).lower()
                if any(k in filename for k in keyword_list):
                    invoice_blob = b
                    break
            
            if invoice_blob:
                logger.info(f"Found invoice using provider keywords: {invoice_blob}")
                for b in pdf_blobs:
                    if b != invoice_blob:
                        clinical_blobs.append(b)
        
        # Fallback to default logic if no invoice found yet
        if not invoice_blob:
            logger.info(f"No invoice found using provider rules for {folder_name}. Using default logic.")
            for b in pdf_blobs:
                filename = os.path.basename(b).lower()
                if "rendicion" in filename or "factura" in filename or "factmed" in filename:
                    invoice_blob = b
                else:
                    clinical_blobs.append(b)
                    
            if not invoice_blob and pdf_blobs:
                logger.warning(f"Scenario Fallback for {folder_name}: Multiple files but no Invoice keyword found. Skipping.")
                return

    # Validation logic
    if not invoice_blob:
        logger.warning(f"Skipping {folder_name}: No invoice found in GCS.")
        return
    
    if not clinical_blobs:
         # This might happen in Scenario 1/2 if only invoice was found [len > 1 but all matched invoice keyword?]
         # Or if list was empty.
         logger.warning(f"Skipping {folder_name}: No Clinical History found in GCS.")
         return

    logger.info(f"  Invoice Blob: {invoice_blob}")
    logger.info(f"  Clinical Blobs: {clinical_blobs}")
    
    # Prepare local temp directory for this folder
    current_temp_dir = os.path.join(local_temp_dir, folder_name)
    os.makedirs(current_temp_dir, exist_ok=True)
    
    local_invoice_path = os.path.join(current_temp_dir, os.path.basename(invoice_blob))
    
    # Download Invoice
    if not gcs_client.download_file(bucket_name, invoice_blob, local_invoice_path):
        logger.error(f"Failed to download invoice: {invoice_blob}")
        return

    local_clinical_paths = []
    for cb in clinical_blobs:
        local_path = os.path.join(current_temp_dir, os.path.basename(cb))
        if gcs_client.download_file(bucket_name, cb, local_path):
            local_clinical_paths.append(local_path)
        else:
            logger.error(f"Failed to download clinical file: {cb}")
            
    if not local_clinical_paths:
        logger.error("No clinical files downloaded successfully.")
        return
        
    # Run Pipeline
    trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    logger.info(f"Generated Trace ID for {folder_name}: {trace_id}")
    upsert_investigation_status(folder_name, 'processing', trace_id=trace_id)
    
    try:
        # We reuse the existing output structure inside temp dir
        file_prefix = f"{folder_name}_"
        
        await run_pipeline(
            invoice_path=local_invoice_path, 
            clinical_paths=local_clinical_paths, 
            output_dir=current_temp_dir, 
            file_prefix=file_prefix,
            user_id="gcs_batch_user", 
            session_id=f"session_{folder_name}"
        )
        logger.info(f"Successfully processed {folder_name} locally.")
        
        # Upload results
        for f in os.listdir(current_temp_dir):
            if f.endswith(".json") or f.endswith(".pdf"):
                local_file_path = os.path.join(current_temp_dir, f)
                destination_blob = f"{folder_prefix}{f}"
                gcs_client.upload_file(bucket_name, local_file_path, destination_blob)
        
        # Trigger Ingestion
        ingest_results(folder_name, current_temp_dir, trace_id=trace_id)
        
        # Move files to processed bucket on success
        # PROCESSED_BUCKET = os.environ.get("PROCESSED_BUCKET", "liquidacionesprocessed")
        # logger.info(f"Moving files from {bucket_name}/{folder_prefix} to {PROCESSED_BUCKET}/{folder_prefix}")
        
        # move_success = gcs_client.move_folder(bucket_name, folder_prefix, PROCESSED_BUCKET, folder_prefix)
        # if not move_success:
        #      logger.error(f"Failed to move files to processed bucket for {folder_name}")
                
    except Exception as e:
        logger.error(f"Error processing {folder_name}: {e}")
        upsert_investigation_status(folder_name, 'failed')
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(current_temp_dir):
            shutil.rmtree(current_temp_dir)

async def main():
    parser = argparse.ArgumentParser(description="Run batch processing from GCS.")
    parser.add_argument("--bucket", required=True, help="GCS Bucket Name")
    parser.add_argument("--prefix", default="data/", help="Prefix in GCS to search for folders (default: data/)")
    args = parser.parse_args()
    
    bucket_name = args.bucket
    base_prefix = args.prefix
    
    # Local temp directory
    local_temp_dir = "temp_gcs_processing"
    if not os.path.exists(local_temp_dir):
        os.makedirs(local_temp_dir)
        
    client = GCSClient()
    
    # List "folders" in the base prefix
    # We might need to handle if the user passed "data" without slash
    if not base_prefix.endswith('/'):
        base_prefix += '/'
        
    logger.info(f"Scanning GCS bucket '{bucket_name}' for folders in '{base_prefix}'...")
    folders = client.list_folders(bucket_name, prefix=base_prefix)
    
    logger.info(f"Found {len(folders)} folders.")
    
    for folder_prefix in folders:

             
        await process_gcs_folder(client, bucket_name, folder_prefix, local_temp_dir)

    # Final cleanup of temp root
    if os.path.exists(local_temp_dir):
        shutil.rmtree(local_temp_dir)

if __name__ == "__main__":
    asyncio.run(main())
