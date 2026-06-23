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
import logging
from typing import List, Optional
from google.cloud import storage

# Configure logging
logger = logging.getLogger(__name__)

class GCSClient:
    def __init__(self):
        """Initializes the GCS client."""
        try:
            self.client = storage.Client()
        except Exception as e:
            logger.error(f"Failed to initialize GCS Client: {e}")
            raise

    def list_files(self, bucket_name: str, prefix: str = "") -> List[str]:
        """
        Lists all files in a bucket with the given prefix.
        
        Args:
            bucket_name: Name of the GCS bucket.
            prefix: Prefix to filter files (acts like a folder).
            
        Returns:
            List of blob names.
        """
        try:
            blobs = self.client.list_blobs(bucket_name, prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing files in {bucket_name}/{prefix}: {e}")
            return []

    def list_folders(self, bucket_name: str, prefix: str = "") -> List[str]:
        """
        Lists 'subdirectories' in a bucket path. 
        GCS uses flat storage, so this simulates folders by looking for unique prefixes.
        
        Args:
            bucket_name: Name of the GCS bucket.
            prefix: Prefix to start looking from.
        
        Returns:
            List of 'folder' names (prefixes ending with /).
        """
        try:
            # We use the iterator's prefixes feature
            # Note: delimiter='/' is important to assume folder structure
            blobs = self.client.list_blobs(bucket_name, prefix=prefix, delimiter='/')
            
            # This triggers the API call and populates prefixes
            # We don't actually need to iterate over blobs if we just want folders (prefixes)
            # preventing full iteration if possible, but list_blobs returns an iterator.
            # We must iterate or call a method to fetch pages to populate prefixes.
            for _ in blobs:
                break
                
            return list(blobs.prefixes)
        except Exception as e:
            logger.error(f"Error listing folders in {bucket_name}/{prefix}: {e}")
            return []

    def download_file(self, bucket_name: str, source_blob_name: str, destination_file_name: str) -> bool:
        """
        Downloads a blob from the bucket.
        
        Args:
            bucket_name: Name of the GCS bucket.
            source_blob_name: The name of the blob to download.
            destination_file_name: The local path to download file to.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(source_blob_name)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
            
            blob.download_to_filename(destination_file_name)
            logger.info(f"Downloaded {source_blob_name} to {destination_file_name}")
            return True
        except Exception as e:
            logger.error(f"Error downloading {source_blob_name}: {e}")
            return False

    def upload_file(self, bucket_name: str, source_file_name: str, destination_blob_name: str) -> bool:
        """
        Uploads a file to the bucket.
        
        Args:
            bucket_name: Name of the GCS bucket.
            source_file_name: Path to the local file.
            destination_blob_name: Name of the blob in storage.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_filename(source_file_name)
            logger.info(f"Uploaded {source_file_name} to {destination_blob_name}")
            return True
        except Exception as e:
            logger.error(f"Error uploading {source_file_name}: {e}")
            return False

    def move_folder(self, source_bucket_name: str, source_prefix: str, dest_bucket_name: str, dest_prefix: str) -> bool:
        """
        Moves all blobs from source prefix to dest prefix (across buckets if needed).
        This is a Copy + Delete operation.
        """
        try:
            source_bucket = self.client.bucket(source_bucket_name)
            dest_bucket = self.client.bucket(dest_bucket_name)
            
            blobs = source_bucket.list_blobs(prefix=source_prefix)
            
            count = 0
            # To iterate blobs and allow prefixes to be populated (if used elsewhere, but here we just iterate)
            for blob in blobs:
                relative_path = blob.name[len(source_prefix):]
                dest_name = f"{dest_prefix}{relative_path}"
                
                # Copy blob
                new_blob = source_bucket.copy_blob(blob, dest_bucket, dest_name)
                logger.info(f"Copied {blob.name} to {dest_bucket_name}/{dest_name}")
                
                # Delete blob from source
                blob.delete()
                logger.debug(f"Deleted source {blob.name}")
                count += 1
                
            logger.info(f"Successfully moved {count} files from {source_prefix} to {dest_bucket_name}/{dest_prefix}")
            return True
        except Exception as e:
            logger.error(f"Error moving folder {source_prefix}: {e}")
            return False

    def file_exists(self, bucket_name: str, blob_name: str) -> bool:
        """Checks if a file exists in the bucket."""
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking existence of {blob_name}: {e}")
            return False
