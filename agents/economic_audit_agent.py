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
    from .schemas import SubAgent4Result, BillingExtractionResult, SubAgent2Result
except ImportError:
    from agents.schemas import SubAgent4Result, BillingExtractionResult, SubAgent2Result

# Define the Economic Audit Agent
economic_audit_agent = LlmAgent(
    name="EconomicAuditAgent",
    model="gemini-3.1-pro-preview",
    description="Performs an economic audit comparing invoiced vs clinical data.",
    instruction="""Perform an economic audit by comparing invoiced medications against what
was actually prescribed and administered (clinical reality).

You will receive:
– One or more billing/invoice PDFs (may include drug name, amount, cost).
– The 'targeted_verification_result' from session state, showing prescribed + administered medications.
– The 'billing_extraction_result' from session state.

Goal: Detect overbilling or inconsistencies per Afiliado. Identify drugs invoiced but not
prescribed or not given, and those billed in excess amounts.

Process:
1. Use the 'billing_extraction_result' to get the list of 'afiliados' and their items.
2. Cross-compare with 'targeted_verification_result' (prescribed + administered):
– Match by normalized_name (fallback original_name), presentation, and
numeric amounts.
– Compute differences between invoiced vs administered vs prescribed.
– **Extract 'administration_date' from 'targeted_verification_result' findings if available.**

Status codes:
MATCH – Invoiced = Prescribed = Administered.
OVERBILLED – Invoiced > Administered or Prescribed.
NOT PRESCRIBED – Invoiced item not ordered in clinical docs.
NOT ADMINISTERED – Invoiced but never administered.

Output:
Produce a structured comparison table with columns:
| Medication | Prescribed | Administered | Administration Date | Invoiced | Discrepancy Type | Unit Cost | Estimated Overbilled Amount | Observation | Page(s) | Source |

Summary:
– Total invoiced items
– % and count for MATCH, OVERBILLED, NOT PRESCRIBED, NOT
ADMINISTERED
– Estimated total overbilling (sum of overbilled units × unit_cost)

Technical appendix (optional):
A) pages_issues → [{page,
issue:["low_quality","rotated","handwriting","cut_text"], comment}]
B) unparsed_candidates → [{raw_line, page, reason}]

Validation rules:
– Always parse numbers as numeric.
– Include source_doc + page for every line.

– If uncertain, mark as OVERBILLED or NOT PRESCRIBED rather than
MATCH.
– End strictly with structured tables + summary (no narrative text).
– Output strictly in JSON format matching the schema.""",
    output_schema=SubAgent4Result,
    output_key="economic_audit_result",
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

async def run_economic_audit(billing_data: dict, verification_data: dict, user_id: str = "test_user", session_id: str = "test_session"):
    """
    Runs the economic audit agent using data from previous steps.
    """
    # Setup session and runner
    session_service = InMemorySessionService()
    
    # Initialize session with data from previous agents
    initial_state = {
        "billing_extraction_result": billing_data,
        "targeted_verification_result": verification_data
    }
    
    session = await session_service.create_session(
        app_name="audit_app",
        user_id=user_id,
        session_id=session_id,
        state=initial_state
    )

    runner = Runner(
        agent=economic_audit_agent,
        app_name="audit_app",
        session_service=session_service
    )

    content = types.Content(role='user', parts=[types.Part(text="Perform the economic audit based on the provided billing and verification data.")])
    
    print(f"Starting economic audit for session {session_id}...")
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
    
    async for event in events:
        pass  # wait for completion

    # Access result
    final_session = await session_service.get_session(app_name="audit_app", user_id=user_id, session_id=session_id)
    
    if final_session:
        state = final_session.state() if callable(final_session.state) else final_session.state
        result = state.get("economic_audit_result")
    else:
        result = None
    
    return result