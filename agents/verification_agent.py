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
import asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.planners import BuiltInPlanner
from google.genai import types

load_dotenv()

try:
    from .schemas import SubAgent2Result, BillingExtractionResult
except ImportError:
    from agents.schemas import SubAgent2Result, BillingExtractionResult

# Define the Verification Agent
verification_agent = LlmAgent(
    name="VerificationAgent",
    model="gemini-3.1-pro-preview",
    description="Performs targeted verification of medications in clinical records.",
    instruction="""Perform a targeted extraction and verification of medications from the attached
clinical record PDF(s).

CRITICAL INSTRUCTION:
CRITICAL INSTRUCTION:
You must ONLY look for the medications that were found in the 'billing_extraction_result' from current session state.
Read the field 'afiliados' from 'billing_extraction_result'.

Goal: For each Afiliado and their billed medications, confirm whether they were (a) prescribed by a
physician and (b) actually administered by nursing staff.

Process:
1. Iterate through each 'Afiliado' in 'billing_extraction_result'.
2. For each medication in that Afiliado's list:
   - Scan clinical PDFs (orders/nursing sheets) specifically looking for that patient's context if possible, or matches in general.
2. For each of those names, scan through all attached clinical PDFs
(medical orders, nursing sheets, etc.) using OCR on every non-digital
page. Rotate/deskew and enhance as needed.
3. Search only for occurrences of those specific medication names (or close
variations, abbreviations, or brands).
4. When a match is found, extract nearby context (same line or neighboring
lines) including: presentation, dosage, route, frequency, and date/time.
5. Classify findings into two groups:
– Prescribed (if appears in physician’s order or indication section)
– Administered (if appears in nursing or administration records)

Output table:
| Medication | Found in Prescriptions | Found in Nursing Records | Administration Date | Dose / Frequency / Route | Match Status | Observation | Page(s) |

Status codes:
MATCH – Found as both prescribed and administered
PARTIAL – Found but incomplete or inconsistent
MISSING – Not found in either prescriptions or nursing notes

Summary:
– Total billed medications reviewed
– Count and % of matches, partials, missing
– List of billed drugs not found in clinical documentation

Technical appendix:
A) pages_issues → [{page, issue:["low_quality","rotated","handwriting","table_layout"], comment}]
B) unparsed_candidates → [{billed_name, raw_line, page, reason}]

Normalization glossary (short):
Paracetamol ≡ Acetaminofén ≡ Tafirol → Paracetamol; Metamizol ≡ Dipirona;
Amoxicilina/Ácido Clavulánico ≡ Clavulin; FA/f a/amp → Ampolla; EV ≡ IV; VO ≡
oral; IM ≡ intramuscular; SC ≡ subcutánea; c/8h ≡ q8h; c/12h ≡ q12h.

Validation rules:
– Parse all numbers as numeric values.
– Always cite page and source document.
– If medication not found, report explicitly in summary.
– Output strictly as structured tables (no narrative text).
– Output strictly in JSON format matching the schema.""",
    output_schema=SubAgent2Result,
    output_key="targeted_verification_result",
    disallow_transfer_to_parent=True,
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=0
        )
    ),
    generate_content_config=types.GenerateContentConfig(
        max_output_tokens=65535
    )
)

async def run_verification(clinical_pdf_path: str, billing_data: dict, user_id: str = "test_user", session_id: str = "test_session"):
    """
    Runs the verification agent to validate billed items against clinical history.
    """
    # Setup session and runner
    session_service = InMemorySessionService()
    
    # Initialize session with billing data
    initial_state = {
        "billing_extraction_result": billing_data
    }
    
    session = await session_service.create_session(
        app_name="verification_app",
        user_id=user_id,
        session_id=session_id,
        state=initial_state
    )

    runner = Runner(
        agent=verification_agent,
        app_name="verification_app",
        session_service=session_service
    )

    # Prepare content with PDF
    parts = []
    if clinical_pdf_path and os.path.exists(clinical_pdf_path):
        import pypdf
        import io
        
        try:
            reader = pypdf.PdfReader(clinical_pdf_path)
            num_pages = len(reader.pages)
            print(f"PDF has {num_pages} pages.")
            
            MAX_PAGES_PER_PART = 900  # Safe limit below 1000
            
            if num_pages > MAX_PAGES_PER_PART:
                print(f"Splitting PDF into chunks of {MAX_PAGES_PER_PART} pages...")
                for i in range(0, num_pages, MAX_PAGES_PER_PART):
                    writer = pypdf.PdfWriter()
                    end_page = min(i + MAX_PAGES_PER_PART, num_pages)
                    
                    for page_num in range(i, end_page):
                        writer.add_page(reader.pages[page_num])
                    
                    pdf_bytes_io = io.BytesIO()
                    writer.write(pdf_bytes_io)
                    pdf_chunk_data = pdf_bytes_io.getvalue()
                    
                    parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=pdf_chunk_data)))
                    print(f"  Added chunk {i}-{end_page} ({len(pdf_chunk_data)} bytes)")
            else:
                # Normal loading
                with open(clinical_pdf_path, "rb") as f:
                    pdf_data = f.read()
                parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=pdf_data)))
                print(f"Loaded Clinical History PDF from {clinical_pdf_path} ({len(pdf_data)} bytes)")
                
        except Exception as e:
            print(f"Error processing PDF: {e}")
            raise
            
    else:
        raise ValueError(f"Clinical history PDF not found at {clinical_pdf_path}")
        
    parts.append(types.Part(text="Please verify the billed medications against the clinical history provided."))

    content = types.Content(role='user', parts=parts)
    
    print(f"Starting verification for session {session_id}...")
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
    
    async for event in events:
        pass  # wait for completion

    # Access result
    final_session = await session_service.get_session(app_name="verification_app", user_id=user_id, session_id=session_id)
    
    if final_session:
        state = final_session.state() if callable(final_session.state) else final_session.state
        result = state.get("targeted_verification_result")
    else:
        result = None
    
    return result
