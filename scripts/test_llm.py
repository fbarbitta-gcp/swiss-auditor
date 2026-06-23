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
import asyncio
from typing import AsyncGenerator
from google.genai import Client
from dotenv import load_dotenv

load_dotenv()

async def test_llm():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    print(f"Testing LLM Connectivity...")
    print(f"Project: {project_id}")
    print(f"Location: {location}")
    
    client = Client(
        vertexai=True,
        project=project_id,
        location=location
    )
    
    print("Sending request to Gemini 2.5 Flash...")
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'Hello, World!' if you can hear me."
        )
        print("\n--- Response ---")
        print(response.text)
        print("----------------")
        print("✅ Connectivity Verified")
    except Exception as e:
        print("\n❌ Connectivity Failed")
        print(e)

if __name__ == "__main__":
    asyncio.run(test_llm())
