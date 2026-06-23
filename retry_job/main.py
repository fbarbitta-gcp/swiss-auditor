import os
import logging
from datetime import datetime, timezone, timedelta
from google.cloud import storage

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retry_job")

def scan_and_retry():
    """Scan liquidacionesraw for failed or missing triggers and recreate/create them."""
    
    # Defaults or overridden via environment variables
    bucket_name = os.environ.get("BUCKET_NAME", "liquidacionesraw")
    age_hours = float(os.environ.get("AGE_HOURS", 2.0))
    
    logger.info(f"Scanning for failed or missing triggers in {bucket_name} (age > {age_hours} hours)")
    
    client = storage.Client()
    
    try:
        bucket = client.bucket(bucket_name)
        blobs = bucket.list_blobs()
    except Exception as e:
        logger.error(f"Failed to access bucket {bucket_name}: {e}")
        return
        
    now = datetime.now(timezone.utc)
    threshold_time = now - timedelta(hours=age_hours)
    
    files_by_folder = {}
    
    for blob in blobs:
        path = blob.name
        folder = os.path.dirname(path) + "/"
        
        if folder not in files_by_folder:
            files_by_folder[folder] = []
        files_by_folder[folder].append((path, blob.time_created))

    count = 0
    
    temp_trigger_path = "/tmp/swiss_auditor_worker_retry.trigger"
    with open(temp_trigger_path, 'w') as f:
         f.write("retry")

    for folder, files in files_by_folder.items():
        if not files:
            continue
            
        # Find newest file to check if older than threshold
        newest_time = max(f[1] for f in files)
        if newest_time > threshold_time:
            continue
            
        has_trigger = any(f[0].endswith(".trigger") for f in files)
        
        # Check if JSON already exists (processing completed, but not moved)
        has_results = any(f[0].lower().endswith(".json") for f in files)
        if has_results:
            logger.info(f"Skipping folder {folder}: Output already exists (JSON found)")
            continue
        
        # Default to autoscan.trigger
        trigger_path = f"{folder}autoscan.trigger"
        
        if has_trigger:
            for f in files:
                if f[0].endswith(".trigger"):
                    trigger_path = f[0]
                    break
            logger.info(f"Re-triggering failed folder: {folder} (overwriting trigger)")
        else:
            if folder == "/":
                continue
            
            # Check if there are any PDFs in the folder to be valid
            has_pdfs = any(f[0].lower().endswith(".pdf") for f in files)
            if not has_pdfs:
                 continue

            logger.info(f"Triggering missing folder: {folder} (creating new trigger)")

        # Upload trigger
        try:
            trigger_blob = bucket.blob(trigger_path)
            trigger_blob.upload_from_filename(temp_trigger_path)
            count += 1
        except Exception as e:
            logger.error(f"Error creating trigger {trigger_path}: {e}")

    logger.info(f"Scanned folders and (re)created {count} triggers.")

if __name__ == "__main__":
    scan_and_retry()
