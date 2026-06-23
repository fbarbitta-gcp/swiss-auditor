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

import argparse
import base64
import json
import logging
from google.cloud import pubsub_v1
from utils.gcs_utils import GCSClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def dispatch_jobs(project_id: str, topic_id: str, bucket_name: str, prefix: str):
    """
    Lists folders in GCS and publishes tasks to Pub/Sub.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    
    gcs_client = GCSClient()
    
    # Ensure prefix ends with slash for folder listing
    if not prefix.endswith('/'):
        prefix += '/'

    logger.info(f"Scanning {bucket_name}/{prefix}...")
    folders = gcs_client.list_folders(bucket_name, prefix=prefix)
    logger.info(f"Found {len(folders)} folders.")
    
    count = 0
    for folder_prefix in folders:
        folder_name = folder_prefix.rstrip('/').split('/')[-1]
        
        # Check if output exists (Optimistic check to save queue space)
        # Note: Worker also checks this, but checking here saves Pub/Sub calls.
        expected_output = f"{folder_prefix}{folder_name}_economic_audit_result.json"
        if gcs_client.file_exists(bucket_name, expected_output):
            logger.debug(f"Skipping {folder_name}: already done.")
            continue
            
        payload = {
            "bucket": bucket_name,
            "folder_prefix": folder_prefix
        }
        data_str = json.dumps(payload)
        data = data_str.encode("utf-8")
        
        future = publisher.publish(topic_path, data)
        # Optional: wait for result or just fire and forget (future.result())
        # validation for demonstration:
        # message_id = future.result()
        
        count += 1
        if count % 100 == 0:
            logger.info(f"Dispatched {count} jobs...")
            
    logger.info(f"Total jobs dispatched: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dispatch batch processing jobs to Pub/Sub.")
    parser.add_argument("--project", required=True, help="Google Cloud Project ID")
    parser.add_argument("--topic", required=True, help="Pub/Sub Topic ID")
    parser.add_argument("--bucket", required=True, help="GCS Bucket Name")
    parser.add_argument("--prefix", default="data/", help="GCS Prefix to scan")
    
    args = parser.parse_args()
    
    dispatch_jobs(args.project, args.topic, args.bucket, args.prefix)
