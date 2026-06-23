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
import io
import sys
from typing import List
from google import genai
from google.genai import types

try:
    import pypdf
except ImportError:
    print("pypdf is not installed. Please install it with `pip install pypdf`")
    # We don't exit here to allow import, but function will fail if used
    pypdf = None

def load_pdf_parts(file_path: str, batch_size: int = 900) -> List[types.Part]:
    """
    Loads a PDF file and returns it as a list of genai.types.Part.
    Splits the PDF into chunks if it exceeds the batch_size (default 900 pages).
    
    Args:
        file_path: Path to the PDF file.
        batch_size: Number of pages per chunk (limit is often 1000).
        
    Returns:
        List of types.Part objects.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    if pypdf is None:
        print("Warning: pypdf not found. Loading file directly without splitting. Large files may fail.")
        with open(file_path, "rb") as f:
            return [types.Part.from_bytes(data=f.read(), mime_type='application/pdf')]

    try:
        reader = pypdf.PdfReader(file_path)
        total_pages = len(reader.pages)
    except Exception as e:
        print(f"Error reading PDF with pypdf: {e}. Falling back to direct read.")
        with open(file_path, "rb") as f:
            return [types.Part.from_bytes(data=f.read(), mime_type='application/pdf')]
    
    if total_pages <= batch_size:
        with open(file_path, "rb") as f:
            return [types.Part.from_bytes(data=f.read(), mime_type='application/pdf')]
            
    print(f"File {file_path} has {total_pages} pages (limit {batch_size}). Splitting...")
    parts = []
    
    for i in range(0, total_pages, batch_size):
        try:
            writer = pypdf.PdfWriter()
            end_page = min(i + batch_size, total_pages)
            for page in reader.pages[i:end_page]:
                writer.add_page(page)
                
            chunk_buffer = io.BytesIO()
            writer.write(chunk_buffer)
            chunk_bytes = chunk_buffer.getvalue()
            parts.append(types.Part.from_bytes(data=chunk_bytes, mime_type='application/pdf'))
            print(f"Created chunk {len(parts)} with pages {i+1}-{end_page}")
        except Exception as e:
            print(f"Error splitting chunk {i}: {e}")
            raise

    return parts

def _count_chunk_tokens(client, chunk_bytes, chunk_index, model):
    """Internal helper to count tokens for a single chunk."""
    print(f"Counting tokens for chunk {chunk_index}...")
    try:
        response = client.models.count_tokens(
            model=model,
            contents=[types.Part.from_bytes(
                data=chunk_bytes,
                mime_type='application/pdf'
            )]
        )
        return response.total_tokens
    except Exception as e:
        print(f"Error counting tokens for chunk {chunk_index}: {e}")
        return 0

def count_pdf_tokens(file_path: str, project_id: str = None, location: str = None, model: str = "gemini-2.5-flash", batch_size: int = 500) -> int:
    """
    Counts tokens in a PDF file using Vertex AI, handling large files by splitting them.
    
    Args:
        file_path: Path to the PDF file.
        project_id: Google Cloud Project ID.
        location: Google Cloud Location (Region).
        model: Model name to use for counting.
        batch_size: Number of pages per chunk (default 500, max 1000 for API).
    
    Returns:
        Total token count.
    """
    if pypdf is None:
        raise ImportError("pypdf is required for PDF processing. Please install it with `pip install pypdf`.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Use default environment variables if not provided
    if not project_id:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not location:
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        
    if not project_id:
        raise ValueError("Project ID must be provided or set in GOOGLE_CLOUD_PROJECT environment variable.")

    print(f"Using Project: {project_id}, Location: {location}")

    try:
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Vertex AI client: {e}")

    print(f"Reading file: {file_path}")
    
    # Check explicitly if we can just reuse load_pdf_parts logic or keep this separate.
    # For now, to minimize risk of breaking existing behavior if it relies on specific splitting/counting interactively, I'll keep the logic but maybe reuse parts?
    # Actually, reusing logic is safer.
    
    # But wait, count_pdf_tokens did splitting and then counting individually.
    # If I use load_pdf_parts, I get a list of Parts. I can then count them.
    
    parts = load_pdf_parts(file_path, batch_size=batch_size)
    total_tokens = 0
    for i, part in enumerate(parts):
        # We need bytes from the part
        if part.inline_data:
             data = part.inline_data.data
        elif part.file_data:
             # If it was file_data (not supported by simple load_pdf_parts yet, which does bytes)
             # load_pdf_parts uses from_bytes so strictly inline_data
             data = part.inline_data.data
        else:
             print("Warning: Unknown part data type")
             continue
             
        chunk_tokens = _count_chunk_tokens(client, data, i + 1, model)
        print(f"Chunk {i+1}: {chunk_tokens} tokens")
        total_tokens += chunk_tokens

    print(f"Total tokens for entire document: {total_tokens}")
    return total_tokens
