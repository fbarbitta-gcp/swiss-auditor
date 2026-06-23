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

import json
import os
import sys

# Mocking the execute_values function to just print what would be inserted
def mock_execute_values(cur, sql, values):
    print(f"SQL: {sql.strip()}")
    print("Values:")
    for v in values:
        print(v)

class MockCursor:
    def execute(self, sql, params=None):
        print(f"Cursor Execute: {sql.strip()} | Params: {params}")

    def close(self):
        pass

class MockConn:
    def cursor(self):
        return MockCursor()
    def commit(self):
        print("Commit")
    def rollback(self):
        print("Rollback")
    def close(self):
        print("Connection Closed")

# Mock psycopg2 before importing the script
from unittest.mock import MagicMock
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()

# Now import the process_folder function
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.ingest_results import process_folder

# Monkey patch execute_values (since we mocked the module, we need to ensure our logic runs if it uses the imported one,
# but actually if we mock the module, the script will import the Mock.
# So we need to override the execute_values in the script module AFTER import if it imported it directly)
import scripts.ingest_results
scripts.ingest_results.execute_values = mock_execute_values

def run_verification():
    # Path to the specific test folder
    folder_path = os.path.abspath("data/25699_UNICO")
    
    conn = MockConn()
    print(f"Testing ingestion for {folder_path}...")
    process_folder(conn, folder_path)

if __name__ == "__main__":
    run_verification()
