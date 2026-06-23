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
import sys

# Add project root to sys.path to allow importing from utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.genai_utils import count_pdf_tokens

def main():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "indigo-splice-412318")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    file_path = os.path.abspath("data/LITVAK JOSE ALBERTO-HIN63366_97.pdf")

    try:
        total_tokens = count_pdf_tokens(
            file_path=file_path,
            project_id=project_id,
            location=location,
            model='gemini-2.5-flash'
        )
        # The util already prints total, but we can print again or do something else
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
