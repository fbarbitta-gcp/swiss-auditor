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
import logging
from typing import Dict, Any, Optional, List

import pypdf
import io

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types, errors
from google.api_core import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from agents.billing_agent import create_billing_agent
from agents.verification_agent import verification_agent
from agents.economic_audit_agent import economic_audit_agent
from utils.genai_utils import load_pdf_parts

def is_transient_error(exception):
    """Returns True if the exception is a 429, 499, or a transient 5xx error."""
    if isinstance(exception, errors.ClientError):
        return any(code in str(exception) for code in ["429", "499"]) or getattr(exception, 'code', 0) in [429, 499]
    if isinstance(exception, errors.ServerError):
        return True
    if isinstance(exception, (exceptions.ResourceExhausted, exceptions.ServiceUnavailable)):
        return True
    return False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.apps.app import App

class RunContext:
    def __init__(self):
        self.total_tokens = 0
        self.models_used = set()
        self.usage_breakdown = {} # { "model": {"prompt": X, "completion": Y} }

class TokenTrackerPlugin(BasePlugin):
    def __init__(self, run_context: RunContext):
        super().__init__("token_tracker")
        self.run_context = run_context

    async def after_model_callback(self, *, callback_context, llm_response):
        if llm_response.usage_metadata:
            self.run_context.total_tokens += llm_response.usage_metadata.total_token_count
            model = llm_response.model_version or "unknown"
            self.run_context.models_used.add(model)
            
            if model not in self.run_context.usage_breakdown:
                self.run_context.usage_breakdown[model] = {"prompt": 0, "completion": 0}
            
            self.run_context.usage_breakdown[model]["prompt"] += getattr(llm_response.usage_metadata, 'prompt_token_count', 0)
            self.run_context.usage_breakdown[model]["completion"] += getattr(llm_response.usage_metadata, 'candidates_token_count', 0)
        return None

async def run_pipeline(invoice_path: Any, clinical_paths: List[str], output_dir: str = "data", file_prefix: str = "", user_id: str = "test_user", session_id: str = "test_session"):
    """
    Runs the pipeline with isolated sessions for each agent.
    
    Args:
        invoice_path: Path to the invoice PDF (str) or List of paths/URIs (List[str]).
        clinical_paths: List of paths to clinical history PDFs.
        output_dir: Directory to save the output JSON files.
        file_prefix: Prefix for the output filenames (e.g., "FolderX_").
        user_id: User ID for the session.
        session_id: Session ID.
    """
    
    run_ctx = RunContext()
    
    # --- Step 1: Billing Extraction ---
    logger.info("--- Step 1: Billing Extraction ---")
    
    # Calculate Complexity (Total Pages)
    total_pages = 0
    invoice_paths = [invoice_path] if isinstance(invoice_path, str) else invoice_path
    for inv_path in invoice_paths:
        if isinstance(inv_path, str) and not inv_path.startswith("gs://") and os.path.exists(inv_path):
            try:
                reader = pypdf.PdfReader(inv_path)
                total_pages += len(reader.pages)
            except Exception as e:
                logger.warning(f"Could not read page count for {inv_path}: {e}")
                
    if total_pages > 100:
        selected_model = "gemini-3.1-pro-preview"
        logger.info(f"Complex document detected ({total_pages} pages). Routing to {selected_model}.")
    else:
        selected_model = "gemini-3-flash-preview"
        logger.info(f"Standard document detected ({total_pages} pages). Using {selected_model}.")

    session_service_billing = InMemorySessionService()
    await session_service_billing.create_session(app_name="swiss_auditor", user_id=user_id, session_id=session_id)
    
    billing_agent = create_billing_agent(model=selected_model)
    billing_app = App(name="swiss_auditor", root_agent=billing_agent, plugins=[TokenTrackerPlugin(run_ctx)])
    billing_runner = Runner(app=billing_app, session_service=session_service_billing)
    
    parts = []
    # Normalize invoice_path to list
    invoice_paths = [invoice_path] if isinstance(invoice_path, str) else invoice_path
    
    for inv_path in invoice_paths:
        # Handle GCS URI or Local Path for Invoice
        if inv_path.startswith("gs://"):
            parts.append(types.Part.from_uri(file_uri=inv_path, mime_type="application/pdf"))
            logger.info(f"Using Invoice GCS URI: {inv_path}")
        elif os.path.exists(inv_path):
            if inv_path.lower().endswith(".txt"):
                with open(inv_path, "r") as f:
                    parts.append(types.Part(text=f.read()))
                logger.info(f"Loaded Invoice Text: {inv_path}")
            else:
                parts.extend(load_pdf_parts(inv_path, batch_size=200))
        else:
            error_msg = f"Invoice not found: {inv_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
    
    content = types.Content(role='user', parts=parts)

    
    # Retry wrapper for billing runner
    @retry(
        retry=retry_if_exception(is_transient_error),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10)
    )
    async def run_billing_with_retry():
        events = billing_runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        async for event in events:
            pass
            
    await run_billing_with_retry()
    await billing_runner.close()
    
    # Retrieve and Save Billing Result
    session = await session_service_billing.get_session(app_name="swiss_auditor", user_id=user_id, session_id=session_id)
    state = session.state() if callable(session.state) else session.state
    billing_result = state.get("billing_result")
    
    if billing_result:
        output_path = os.path.join(output_dir, f"{file_prefix}billing_result.json")
        with open(output_path, "w") as f:
            json.dump(billing_result, f, indent=2)
        logger.info(f"Saved {output_path}")
    else:
        logger.warning("No billing result found. Aborting.")
        return

    # --- Step 1.5: Medication Matching ---
    logger.info("--- Step 1.5: Medication Matching ---")
    matched_result = None
    
    if billing_result and "afiliados" in billing_result:
        all_meds = []
        for afiliado in billing_result["afiliados"]:
             all_meds.extend(afiliado.get("medications", []))
             
        if all_meds:
             try:
                 from agents.matching_agent import run_matching
                 # Locate graph
                 graph_path = os.path.join(os.path.dirname(__file__), "resources", "data_grafo_structured.md")
                 
                 logger.info(f"Running matches against {graph_path} for {len(all_meds)} items...")
                 @retry(
                     retry=retry_if_exception(is_transient_error),
                     wait=wait_exponential(multiplier=2, min=4, max=60),
                     stop=stop_after_attempt(10)
                 )
                 async def run_matching_with_retry():
                     return await run_matching(all_meds, graph_path=graph_path, user_id=user_id, session_id=f"{session_id}_matching")
                 
                 match_output = await run_matching_with_retry()
                 
                 if match_output:
                      matched_result = match_output
                      output_path = os.path.join(output_dir, f"{file_prefix}matched_result.json")
                      with open(output_path, "w", encoding="utf-8") as f:
                           json.dump(match_output, f, ensure_ascii=False, indent=2)
                      logger.info(f"Saved {output_path}")
                      
                      # Back-Propagate matched fields into billing_result for downstream agents
                      matches_by_key = {}
                      for m_item in match_output.get("items", []):
                          key = (m_item.get("medication_name"), m_item.get("presentation"))
                          matches_by_key[key] = m_item
                          
                      for afiliado in billing_result.get("afiliados", []):
                          for item in afiliado.get("medications", []):
                              key = (item.get("medication_name"), item.get("presentation"))
                              m_match = matches_by_key.get(key)
                              if m_match:
                                  item["matched_droga_principal"] = m_match.get("matched_droga_principal")
                                  item["matched_presentacion"] = m_match.get("matched_presentacion")
                                  item["match_score"] = m_match.get("match_score")
                                  
                                  # Optional overwrite for transparency in downstream state
                                  # If matched, we can provide it as additional context
                 else:
                      logger.warning("No matching results generated.")
             except Exception as e:
                 logger.error(f"Error running matching agent: {e}")

    # --- Step 2: Targeted Verification ---

    logger.info("--- Step 2: Targeted Verification ---")
    session_service_verification = InMemorySessionService()
    
    # Inject billing result into initial state
    initial_state_verification = {
        "billing_extraction_result": billing_result
    }
    
    await session_service_verification.create_session(
        app_name="swiss_auditor", 
        user_id=user_id, 
        session_id=session_id,
        state=initial_state_verification
    )
    
    verification_app = App(name="swiss_auditor", root_agent=verification_agent, plugins=[TokenTrackerPlugin(run_ctx)])
    verification_runner = Runner(app=verification_app, session_service=session_service_verification)
    
    parts = []
    
    if not clinical_paths:
        logger.warning(f"No clinical PDF paths provided.")
        
    for path in clinical_paths:
        if path.startswith("gs://"):
            parts.append(types.Part.from_uri(file_uri=path, mime_type="application/pdf"))
            logger.info(f"Using Clinical GCS URI: {path}")
            continue

        if os.path.exists(path):
            try:
                reader = pypdf.PdfReader(path)
                num_pages = len(reader.pages)
                logger.info(f"Processing Clinical PDF: {path} ({num_pages} pages).")
                
                # Reduced chunk size to avoid 503 errors and context overload
                MAX_PAGES = 200 
                
                if num_pages > MAX_PAGES:
                    logger.info(f"Splitting clinical PDF {os.path.basename(path)} into chunks of {MAX_PAGES} pages...")
                    for i in range(0, num_pages, MAX_PAGES):
                        writer = pypdf.PdfWriter()
                        end_page = min(i + MAX_PAGES, num_pages)
                        
                        # Add pages to writer
                        for p in range(i, end_page):
                            writer.add_page(reader.pages[p])
                            
                        buf = io.BytesIO()
                        writer.write(buf)
                        doc_bytes = buf.getvalue()
                        
                        parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=doc_bytes)))
                        logger.info(f"  Added PDF chunk {i}-{end_page} ({len(doc_bytes)} bytes)")
                else:
                    if path.lower().endswith(".txt"):
                        with open(path, "r") as f:
                             parts.append(types.Part(text=f.read()))
                        logger.info(f"Loaded Clinical Text: {path}")
                    else:
                        with open(path, "rb") as f:
                            parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=f.read())))
                        logger.info(f"Loaded Clinical PDF: {path}")
            except Exception as e:
                logger.error(f"Error reading clinical PDF {path}: {e}")
                # We continue with other files even if one fails
        else:
             logger.warning(f"Clinical file not found: {path}")
            
    # Inject Billing Result Text
    billing_text = json.dumps(billing_result, indent=2)
    parts.append(types.Part(text=f"Billing Extraction Result:\n{billing_text}"))
    parts.append(types.Part(text="Verify these billed items against the provided clinical history."))
    content = types.Content(role='user', parts=parts)
    
    # Retry wrapper for verification runner
    @retry(
        retry=retry_if_exception(is_transient_error),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10)
    )
    async def run_verification_with_retry():
        events = verification_runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        async for event in events:
            pass
            
    await run_verification_with_retry()
    await verification_runner.close()
    
    # Retrieve and Save Verification Result
    session = await session_service_verification.get_session(app_name="swiss_auditor", user_id=user_id, session_id=session_id)
    state = session.state() if callable(session.state) else session.state
    # The output key in Verification Agent should be "targeted_verification_result"
    verification_result = state.get("targeted_verification_result")
    
    if verification_result:
        output_path = os.path.join(output_dir, f"{file_prefix}targeted_verification_result.json")
        with open(output_path, "w") as f:
            json.dump(verification_result, f, indent=2)
        logger.info(f"Saved {output_path}")
    else:
        logger.warning("No verification result found.")

    # --- Step 3: Economic Audit ---
    logger.info("--- Step 3: Economic Audit ---")
    session_service_audit = InMemorySessionService()
    
    initial_state_audit = {
        "billing_extraction_result": billing_result,
        "targeted_verification_result": verification_result
    }
    
    await session_service_audit.create_session(
        app_name="swiss_auditor", 
        user_id=user_id, 
        session_id=session_id,
        state=initial_state_audit
    )
    
    audit_app = App(name="swiss_auditor", root_agent=economic_audit_agent, plugins=[TokenTrackerPlugin(run_ctx)])
    audit_runner = Runner(app=audit_app, session_service=session_service_audit)
    
    parts_audit = []
    # Re-inject Invoice PDF if needed for context
    invoice_paths = [invoice_path] if isinstance(invoice_path, str) else invoice_path
    
    for inv_path in invoice_paths:
        if inv_path.startswith("gs://"):
            parts_audit.append(types.Part.from_uri(file_uri=inv_path, mime_type="application/pdf"))
        elif os.path.exists(inv_path):
            if inv_path.lower().endswith(".txt"):
                with open(inv_path, "r") as f:
                    parts_audit.append(types.Part(text=f.read()))
            else:
                parts_audit.extend(load_pdf_parts(inv_path, batch_size=200))
    
    # Inject Previous Results
    billing_text = json.dumps(billing_result, indent=2)
    if verification_result:
        verification_text = json.dumps(verification_result, indent=2)
    else:
        verification_text = "No verification result available."

    parts_audit.append(types.Part(text=f"Billing Extraction Result:\n{billing_text}"))
    parts_audit.append(types.Part(text=f"Targeted Verification Result:\n{verification_text}"))
    parts_audit.append(types.Part(text="Perform the economic audit based on the provided data."))

    content = types.Content(role='user', parts=parts_audit)
    
    # Retry wrapper for audit runner
    @retry(
        retry=retry_if_exception(is_transient_error),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10)
    )
    async def run_audit_with_retry():
        events = audit_runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        async for event in events:
            pass
            
    await run_audit_with_retry()
    await audit_runner.close()
    
    # Retrieve and Save Audit Result
    session = await session_service_audit.get_session(app_name="swiss_auditor", user_id=user_id, session_id=session_id)
    state = session.state() if callable(session.state) else session.state
    audit_result = state.get("economic_audit_result")
    
    if audit_result:
        output_path = os.path.join(output_dir, f"{file_prefix}economic_audit_result.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, indent=2)
        logger.info(f"Saved {output_path}")

    # --- Step 4: Consolidation & PDF Generation ---
    logger.info("--- Step 4: Consolidation & PDF Generation ---")
    from agents.consolidation_agent import consolidation_agent
    from agents.pdf_generator import generate_pdf
    
    session_service_consolidation = InMemorySessionService()
    
    initial_state_consolidation = {
        "billing_extraction_result": billing_result,
        "targeted_verification_result": verification_result,
        "economic_audit_result": audit_result
    }
    
    await session_service_consolidation.create_session(
        app_name="swiss_auditor", 
        user_id=user_id, 
        session_id=session_id,
        state=initial_state_consolidation
    )
    
    consolidation_app = App(name="swiss_auditor", root_agent=consolidation_agent, plugins=[TokenTrackerPlugin(run_ctx)])
    consolidation_runner = Runner(app=consolidation_app, session_service=session_service_consolidation)
    
    parts_consolidation = []
    billing_text = json.dumps(billing_result, indent=2) if billing_result else "No billing result."
    verification_text = json.dumps(verification_result, indent=2) if verification_result else "No verification result."
    audit_text = json.dumps(audit_result, indent=2) if audit_result else "No audit result."
    
    parts_consolidation.append(types.Part(text=f"Billing Extraction Result:\n{billing_text}"))
    parts_consolidation.append(types.Part(text=f"Targeted Verification Result:\n{verification_text}"))
    parts_consolidation.append(types.Part(text=f"Economic Audit Result:\n{audit_text}"))
    parts_consolidation.append(types.Part(text="Given the results above, please generate the consolidated report in Spanish."))
    
    content = types.Content(role='user', parts=parts_consolidation)
    
    @retry(
        retry=retry_if_exception(is_transient_error),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(10)
    )
    async def run_consolidation_with_retry():
        events = consolidation_runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        async for event in events:
            pass
            
    await run_consolidation_with_retry()
    await consolidation_runner.close()
    
    # Retrieve and Save Consolidation Result
    session = await session_service_consolidation.get_session(app_name="swiss_auditor", user_id=user_id, session_id=session_id)
    state = session.state() if callable(session.state) else session.state
    consolidation_result = state.get("consolidation_result")
    
    if consolidation_result:
        output_path_md = os.path.join(output_dir, f"{file_prefix}consolidation_result.md")
        with open(output_path_md, "w", encoding="utf-8") as f:
            f.write(str(consolidation_result))
        logger.info(f"Saved {output_path_md}")
        
        # Generate PDF
        pdf_path = os.path.join(output_dir, f"{file_prefix}audit_report.pdf")
        generate_pdf(consolidation_result, pdf_path)
        logger.info(f"Saved Consolidation PDF: {pdf_path}")
        
    # Save run stats
    stats = {
        "total_tokens": run_ctx.total_tokens,
        "models_used": list(run_ctx.models_used),
        "usage_breakdown": run_ctx.usage_breakdown
    }
    stats_path = os.path.join(output_dir, f"{file_prefix}run_stats.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Saved Run Stats: {stats_path}")

    return state

