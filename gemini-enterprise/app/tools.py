import os
import logging
from typing import List, Dict, Any
from google.cloud import storage
import pypdf
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# AlloyDB Config (from environment variables)
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

DEFAULT_BUCKET = os.environ.get("GCS_BUCKET", "swiss-auditor-data-swiss-auditor-service-8d607776-f03c7ee3")

def list_gcs_files(investigation_id: str) -> Dict[str, Any]:
    """Lists all files in GCS for the given investigation.

    Args:
        investigation_id: The ID of the investigation.

    Returns:
        A dictionary with 'status' and 'files' (list of full file paths).
    """
    try:
        client = storage.Client()
        bucket = client.bucket(DEFAULT_BUCKET)
        prefix = f"{investigation_id}/"
        blobs = bucket.list_blobs(prefix=prefix)
        files = [blob.name for blob in blobs]
        return {"status": "success", "files": files}
    except Exception as e:
        logger.error(f"Error listing files for investigation {investigation_id} in {DEFAULT_BUCKET}: {e}")
        return {"status": "error", "message": str(e)}

def read_gcs_file(file_path: str) -> Dict[str, Any]:
    """Reads the content of a file from GCS. Supports .pdf and .json.

    Args:
        file_path: The full path of the file in GCS (e.g., 'data/ID/file.pdf').

    Returns:
        A dictionary with 'status' and 'content' (string for text/pdf, dict for json).
    """
    local_path = f"/tmp/{os.path.basename(file_path)}"
    try:
        client = storage.Client()
        bucket = client.bucket(DEFAULT_BUCKET)
        blob = bucket.blob(file_path)
        
        if not blob.exists():
            return {"status": "error", "message": f"File {file_path} not found in bucket {DEFAULT_BUCKET}"}

        blob.download_to_filename(local_path)

        if file_path.lower().endswith(".pdf"):
            reader = pypdf.PdfReader(local_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            if os.path.exists(local_path):
                 os.remove(local_path)
            return {"status": "success", "content": text}
        
        elif file_path.lower().endswith(".json"):
            import json
            with open(local_path, 'r') as f:
                content = json.load(f)
            if os.path.exists(local_path):
                 os.remove(local_path)
            return {"status": "success", "content": content}
        
        else:
            if os.path.exists(local_path):
                 os.remove(local_path)
            return {"status": "error", "message": "Unsupported file type. Only .pdf and .json are supported."}

    except Exception as e:
        logger.error(f"Error reading file {file_path} from {DEFAULT_BUCKET}: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        return {"status": "error", "message": str(e)}

import httpx
import google.oauth2.id_token
import google.auth.transport.requests

TOOLS_SERVER_URL = os.environ.get("TOOLS_SERVER_URL", "")

def get_google_auth_headers() -> dict:
    """Generates an identity token header for making secure fully-managed Cloud Run calls."""
    try:
        auth_req = google.auth.transport.requests.Request()
        # ID Token required for Cloud Run IAM, using TOOLS_SERVER_URL as Audience
        token = google.oauth2.id_token.fetch_id_token(auth_req, TOOLS_SERVER_URL)
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        logger.warning(f"Could not generate identity token: {e}")
        return {}

def query_alloydb(query: str) -> Dict[str, Any]:
    """Executes a SELECT query on AlloyDB via the Cloud Run proxy.

    Args:
        query: The SQL query string to execute. MUST be a SELECT statement.

    Returns:
        A dictionary with 'status' and 'results' (list of rows as dicts).
    """
    if not query.strip().lower().startswith("select"):
         return {"status": "error", "message": "Only SELECT queries are allowed."}

    if not TOOLS_SERVER_URL:
         return {"status": "error", "message": "TOOLS_SERVER_URL environment variable is not set."}

    try:
        headers = get_google_auth_headers()
        response = httpx.post(
            f"{TOOLS_SERVER_URL}/query", 
            json={"query": query},
            headers=headers,
            timeout=30.0
        )
        if response.status_code != 200:
             return {"status": "error", "message": f"Proxy returned error {response.status_code}: {response.text}"}
        return response.json()
    except Exception as e:
         logger.error(f"AlloyDB proxy query error: {e}")
         return {"status": "error", "message": str(e)}
