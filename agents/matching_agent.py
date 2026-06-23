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
from google.adk.apps.app import App
from google.adk.planners import BuiltInPlanner
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.genai import types

load_dotenv()

try:
    from .schemas import MatchingResult
except ImportError:
    from agents.schemas import MatchingResult

# Locate default graph file relative to this module to read once on load
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_GRAPH_PATH = os.path.join(_CURRENT_DIR, "resources", "data_grafo_structured.md")

try:
    if os.path.exists(_DEFAULT_GRAPH_PATH):
        with open(_DEFAULT_GRAPH_PATH, 'r', encoding='utf-8') as f:
            graph_text = f.read()
    else:
        graph_text = "Graph file not found."
except Exception as e:
    graph_text = f"Error reading graph file: {e}"

matching_agent = LlmAgent(
    name="MatchingAgent",
    model="gemini-3.1-pro-preview", 
    description="Matches extracted medications against a reference Drug Graph to verify equivalent generic names.",
    instruction=f"""You are a medical data auditor.
You are provided with standard reference data. 

**Drug Graph Context**:
{graph_text}

For EACH extracted medication item provided in the message:
-   Look for a matching generic `droga_principal` node in the graph above.
-   If `medication_name` appears to be a **Commercial Name** (Brand), link it to its parent drug node as `matched_droga_principal`.
-   If it describes a **Generic Name**, match it directly to the drug node.
-   Verify if the `presentation` aligns with any of the valid presentations listed for that drug node. If it is similar or implied, flag appropriately.
-   Classify `match_score` as:
    -   `EXACT`: Matching item precisely found for both generic/commercial name and presentacion.
    -   `PARTIAL`: Matching drug found, but presentation differed slightly or is unknown.
    -   `NONE`: Drug or brand not found in reference graph.

Return a list of items containing only the medication_name, presentation, matched_droga_principal, matched_presentacion, match_score, and reasoning for each item processed. Do NOT return other fields like amount, total_cost, or source_page.
""",
    output_schema=MatchingResult,
    output_key="matched_result",
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

matching_app = App(
    name="matching_app",
    root_agent=matching_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=3600,
        cache_intervals=10
    )
)

async def run_matching(medications_list: list, graph_path: str = "agents/resources/data_grafo_structured.md", user_id: str = "test_user", session_id: str = "test_session"):
    """
    Runs the matching agent on a list of medications using the Graph context.
    """
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="matching_app", user_id=user_id, session_id=session_id)

    # Use the global matching_app which has ContextCacheConfig enabled
    runner = Runner(app=matching_app, session_service=session_service)

    # Construct Prompt (The Graph is now in instructions for Context Caching)
    prompt = f"""
Below is the list of **Extracted Medications** to verify:
```json
{json.dumps(medications_list, indent=2)}
```

Perform the matching based on the reference data provided in the system instructions and output according to instructions into standard JSON.
"""

    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
    async for event in events:
        pass

    final_session = await session_service.get_session(app_name="matching_app", user_id=user_id, session_id=session_id)
    if final_session:
        state = final_session.state() if callable(final_session.state) else final_session.state
        result = state.get("matched_result")
    else:
        result = None
        
    await runner.close()
    return result
