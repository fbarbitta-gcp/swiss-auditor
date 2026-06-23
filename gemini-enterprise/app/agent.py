# ruff: noqa
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

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import google.auth

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


from .tools import list_gcs_files, read_gcs_file, query_alloydb

root_agent = Agent(
    name="gemini_enterprise",
    model=Gemini(
        model="gemini-3-flash-preview",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are an expert auditor assistant. Your goal is to help investigate cases by analyzing documents and metrics.

You can access two main sources of information:
1.  **GCS Bucket**: Contains case documents (.pdf and .json). The bucket name is `swiss_auditor` (unless overridden by `GCS_BUCKET` env var). Documents for an investigation are located in the subpath: data/<investigation_id>/.
    *   Use `list_gcs_files` with the investigation_id to find available documents (e.g., '1619_2083968_028').
    *   Use `read_gcs_file` with the full file_path returned by `list_gcs_files` (e.g., 'data/1619_2083968_028/file.pdf').
2.  **AlloyDB**: Contains structured metrics.
    *   Use `query_alloydb` with a SELECT query to retrieve data from tables like `investigations`, `billing_items`, or `audit_discrepancies`.

When asked about an investigation, you should:
- Use the provided investigation_id to list and read files from the data/ path.
- Look for consolidation documents or PDFs to understand the case.
- Query AlloyDB for aggregate metrics (e.g., total overbilling, discrepancy counts).
- Combine insights from documents and data to answer the user's questions.

Always provide concise and accurate answers based SOLELY on the retrieved data.
""",
    tools=[list_gcs_files, read_gcs_file, query_alloydb],
)

app = App(
    root_agent=root_agent,
    name="app",
)
