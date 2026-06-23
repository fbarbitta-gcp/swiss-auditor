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
    from .schemas import BillingExtractionResult
except ImportError:
    from agents.schemas import BillingExtractionResult

# Define the Billing Agent
def create_billing_agent(model="gemini-3.1-pro-preview"):
    """Creates a billing extraction agent configured with the given model."""
    return LlmAgent(
        name="BillingExtractionAgent",
        model=model,
        description="Extracts medication data from billing documents.",
        instruction="""You are a medical billing expert.
Extract all medications from the provided billing/consumption document.
Group them by 'Afiliado' (Patient/Beneficiary Name).

Validation Rules:
1. Capture every listed item — no omissions or duplicates.
2. Group items by the Afiliado Name they belong to.
3. Preserve the original naming as written in the document.
4. Normalize amounts and costs to standard float format.
5. Output strictly in JSON format matching the schema.
6. **Do NOT extract disposable medical supplies (materiales descartables / insumos)**. This includes items like jeringas, agujas, gasas, guantes, guías/tubuladuras, camisolines, etc. ONLY extract pharmaceutical drugs/medications.""",
        output_schema=BillingExtractionResult,
        output_key="billing_result",
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

async def run_billing_extraction(file_path: str = None, text_content: str = None, user_id: str = "test_user", session_id: str = "test_session"):
    """
    Runs the billing agent to extract data from the invoice text or PDF file.
    """
    # Setup session and runner
    session_service = InMemorySessionService()
    
    # create_session is async
    session = await session_service.create_session(
        app_name="billing_app",
        user_id=user_id,
        session_id=session_id
    )

    runner = Runner(
        agent=create_billing_agent(),
        app_name="billing_app",
        session_service=session_service
    )

    # Prepare content
    parts = []
    if file_path:
        with open(file_path, "rb") as f:
            pdf_data = f.read()
        parts.append(types.Part(inline_data=types.Blob(mime_type="application/pdf", data=pdf_data)))
        print(f"Loaded PDF from {file_path} ({len(pdf_data)} bytes)")
    elif text_content:
        parts.append(types.Part(text=text_content))
    else:
        raise ValueError("Either file_path or text_content must be provided.")

    content = types.Content(role='user', parts=parts)
    
    print(f"Starting billing extraction for session {session_id}...")
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
    
    async for event in events:
        pass

    # Access the structured result from session state
    final_session = await session_service.get_session(app_name="billing_app", user_id=user_id, session_id=session_id)
    
    # Check if state is a method or property
    if final_session:
        state = final_session.state() if callable(final_session.state) else final_session.state
        result = state.get("billing_result")
    else:
        result = None
    
    return result