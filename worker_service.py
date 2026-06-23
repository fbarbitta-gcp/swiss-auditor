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
import json
from datetime import datetime, timezone, timedelta
import base64
import asyncio
import logging
from threading import Thread
from flask import Flask, request, jsonify
from utils.gcs_utils import GCSClient
from run_batch_gcs import process_gcs_folder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize GCS Client once
gcs_client = GCSClient()

# Removed global background_loop to prevent event-loop conflicts.
# Background tasks will now cleanly initialize their own event loop using asyncio.run()


@app.route("/", methods=["POST"])
def index():
    """Receive and process Pub/Sub messages."""
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        logger.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        logger.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        try:
            data = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
            # Expecting JSON payload: {"bucket": "...", "folder_prefix": "..."}
            # Or just raw string if simpler, but JSON is safer.
            payload = json.loads(data)
            
            # Handle standard dispatch_jobs.py payload
            if "folder_prefix" in payload:
                bucket_name = payload.get("bucket")
                folder_prefix = payload.get("folder_prefix")
            
            # Handle GCS Object Finalize (Eventarc/PubSub) payload
            elif "name" in payload and "bucket" in payload:
                # GCS event: payload["name"] is the file path (e.g., data/folder/file.pdf)
                file_path = payload["name"]
                bucket_name = payload["bucket"]
                
                # Logic: Only trigger if it looks like a file in a folder we want to process
                # We derive the folder prefix from the file path.
                # Example: data/25966_.../file.pdf -> data/25966_.../
                if "/" in file_path:
                    folder_path = os.path.dirname(file_path)
                    folder_prefix = f"{folder_path}/"
                else:
                    logger.info(f"Ignoring root file: {file_path}")
                    return "Ignored root file", 200

                # STRICT TRIGGER LOGIC:
                # GCS fires an event for EVERY file. To avoid N runs and race conditions (processing before all files are uploaded),
                # we ONLY trigger when a specific "marker" file is uploaded (e.g. "_START.trigger").
                # The user must upload the folder content, and finally upload this marker file.
                if not file_path.endswith(".trigger"):
                    logger.info(f"Ignoring non-trigger file: {file_path}. Upload a .trigger file to start.")
                    return "Ignored non-trigger file", 200
            else:
                 logger.error("Unknown payload format")
                 return "Unknown payload format", 400

            if not bucket_name or not folder_prefix:
                logger.error("Missing bucket or folder_prefix in payload")
                return "Missing args", 400

            logger.info(f"Received task for: {bucket_name}/{folder_prefix}")
            
            # Local temp dir for this specific request
            local_temp_dir = "/tmp/swiss_auditor_worker"
            
            # ASYNC PROCESSING SCHEME
            # 1. Return 200 OK immediately to satisfy Pub/Sub (prevent redelivery).
            # 2. Process in a background thread (requires --no-cpu-throttling).
            # 3. Handle retries internally since Pub/Sub won't retry for us anymore.
            
            from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

            @retry(
                stop=stop_after_attempt(3), 
                wait=wait_exponential(multiplier=1, min=4, max=10),
                retry=retry_if_exception_type(Exception)
            )
            async def run_with_retries_async(client, bucket, prefix, temp_dir):
                logger.info(f"Starting background processing attempt for {prefix}")
                try:
                    await process_gcs_folder(client, bucket, prefix, temp_dir)
                except Exception as e:
                    logger.error(f"Attempt failed for {prefix}: {e}")
                    raise e # Trigger retry

            async def background_worker_async(client, bucket, prefix, temp_dir):
                try:
                    await run_with_retries_async(client, bucket, prefix, temp_dir)
                    logger.info(f"Background processing completely finished for {prefix}")
                except Exception as e:
                    logger.critical(f"All retries failed for {prefix}: {e}")

            def thread_target(client, bucket, prefix, temp_dir):
                asyncio.run(background_worker_async(client, bucket, prefix, temp_dir))

            Thread(target=thread_target, args=(gcs_client, bucket_name, folder_prefix, local_temp_dir), daemon=True).start()
            
            return "Processing started in background", 200

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Returning 500 triggers Pub/Sub retry
            return f"Internal Server Error: {e}", 500

    return "No data found", 400



if __name__ == "__main__":
    # Local development
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
