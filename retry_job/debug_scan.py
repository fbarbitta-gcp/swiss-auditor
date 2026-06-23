import os
import logging
from datetime import datetime, timezone, timedelta
from google.cloud import storage

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retry_job_debug")

def scan_and_retry():
    bucket_name = "liquidacionesraw"
    age_hours = 2.0
    logger.info(f"Scanning for failed or missing triggers in {bucket_name} (age > {age_hours} hours)")
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix="HPR HCs para IA/")
    
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

    for folder, files in files_by_folder.items():
        if "LENARDUZZI" not in folder:
             pass # just debug all. Well, we'll see LENARDUZZI
             
        newest_time = max(f[1] for f in files)
        
        has_trigger = any(f[0].endswith(".trigger") for f in files)
        has_results = any(f[0].lower().endswith(".json") for f in files)
        has_pdfs = any(f[0].lower().endswith(".pdf") for f in files)
        
        logger.info(f"Folder: {folder}")
        logger.info(f"  Newest time: {newest_time} | Threshold: {threshold_time}")
        logger.info(f"  Age OK (needs processing): {newest_time <= threshold_time}")
        logger.info(f"  Has trigger: {has_trigger} | Has results: {has_results} | Has PDFs: {has_pdfs}")
        
scan_and_retry()
