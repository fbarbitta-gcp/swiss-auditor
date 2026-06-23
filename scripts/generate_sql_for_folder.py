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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def escape_sql_string(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return str(value)

def escape_sql_array(value):
    if not value:
        return "'{}'"
    # Convert list to Postgres array string: {1,2,3}
    return "'{" + ",".join(str(v) for v in value) + "}'"

def generate_sql(folder_path, output_file):
    folder_name = os.path.basename(folder_path.rstrip('/'))
    
    billing_file = os.path.join(folder_path, f"{folder_name}_billing_result.json")
    audit_file = os.path.join(folder_path, f"{folder_name}_economic_audit_result.json")
    
    if not os.path.exists(audit_file):
        logger.error(f"Economic audit file not found: {audit_file}")
        return

    # Load data
    with open(audit_file, 'r') as f:
        audit_data = json.load(f)
    
    billing_data = {}
    if os.path.exists(billing_file):
        with open(billing_file, 'r') as f:
            billing_data = json.load(f)

    with open(output_file, 'w') as sql:
        sql.write(f"-- Ingestion script for {folder_name}\n")
        sql.write("BEGIN;\n\n")

        # 1. Investigations
        sql.write("-- 1. Insert/Update Investigation\n")
        
        total_invoiced = audit_data.get("total_invoiced_items", 0)
        pct_match = audit_data.get("percent_match", 0.0)
        pct_over = audit_data.get("percent_overbilled", 0.0)
        pct_np = audit_data.get("percent_not_prescribed", 0.0)
        pct_na = audit_data.get("percent_not_administered", 0.0)
        est_over = audit_data.get("estimated_total_overbilling", 0.0)

        # Assuming processed_at is NOW() for this manual script, or we could leave it default
        # But per schema processed_at DEFAULT NOW(), checking if we want to override it or let update handle it
        # The python script used datetime.now(), we can use CURRENT_TIMESTAMP
        
        insert_inv = f"""INSERT INTO investigations (
    id, 
    status, 
    total_invoiced_items, 
    percent_match, 
    percent_overbilled, 
    percent_not_prescribed, 
    percent_not_administered, 
    estimated_total_overbilling
) VALUES (
    {escape_sql_string(folder_name)},
    'processed',
    {total_invoiced},
    {pct_match},
    {pct_over},
    {pct_np},
    {pct_na},
    {est_over}
)
ON CONFLICT (id) DO UPDATE SET
    processed_at = CURRENT_TIMESTAMP,
    status = EXCLUDED.status,
    total_invoiced_items = EXCLUDED.total_invoiced_items,
    percent_match = EXCLUDED.percent_match,
    percent_overbilled = EXCLUDED.percent_overbilled,
    percent_not_prescribed = EXCLUDED.percent_not_prescribed,
    percent_not_administered = EXCLUDED.percent_not_administered,
    estimated_total_overbilling = EXCLUDED.estimated_total_overbilling;
\n"""
        sql.write(insert_inv)

        # 2. Billing Items
        sql.write(f"\n-- 2. Billings Items\n")
        sql.write(f"DELETE FROM billing_items WHERE investigation_id = {escape_sql_string(folder_name)};\n")
        
        # Check for matched results first (contains optimized names)
        matched_file = os.path.join(folder_path, f"{folder_name}_matched_result.json")
        items_to_insert = []
        
        if os.path.exists(matched_file):
            logger.info(f"Found matched results file: {matched_file}")
            with open(matched_file, 'r') as f:
                matched_data = json.load(f)
                items_to_insert = matched_data.get("items", [])
        elif "medications" in billing_data:
            logger.info(f"Using raw extracted medications from: {billing_file}")
            items_to_insert = billing_data["medications"]

        if items_to_insert:
            sql.write("INSERT INTO billing_items (investigation_id, medication_name, presentation, amount, cost_per_unit, total_cost, source_page) VALUES\n")
            values_list = []
            for item in items_to_insert:
                # Prefer matched name if available and not NONE
                med_name = item.get('matched_droga_principal') or item.get('medication_name')
                pres_name = item.get('matched_presentacion') or item.get('presentation')
                
                # Make sure string isn't an empty string or None mapped from NONE score
                if not med_name:
                     med_name = item.get('medication_name')
                if not pres_name:
                     pres_name = item.get('presentation')

                val = f"({escape_sql_string(folder_name)}, {escape_sql_string(med_name)}, {escape_sql_string(pres_name)}, {item.get('amount', 'NULL')}, {item.get('cost_per_unit', 'NULL')}, {item.get('total_cost', 'NULL')}, {item.get('source_page', 'NULL')})"
                values_list.append(val)
            sql.write(",\n".join(values_list))
            sql.write(";\n")


        # 3. Audit Discrepancies
        sql.write(f"\n-- 3. Audit Discrepancies\n")
        sql.write(f"DELETE FROM audit_discrepancies WHERE investigation_id = {escape_sql_string(folder_name)};\n")
        
        if "discrepancies" in audit_data:
            sql.write("INSERT INTO audit_discrepancies (investigation_id, medication_name, prescribed_text, administered_text, invoiced_text, discrepancy_type, unit_cost, estimated_overbilled_amount, observation, source_pages) VALUES\n")
            values_list = []
            for item in audit_data["discrepancies"]:
                pages = item.get("pages", [])
                # Handle boolean logic for numeric fields if they are strings in json?? 
                # Inspecting JSON: "prescribed": "2.0", "unit_cost": 21049.64 (number)
                # "estimated_overbilled_amount": 0.0 (number)
                
                val = f"({escape_sql_string(folder_name)}, {escape_sql_string(item.get('medication'))}, {escape_sql_string(item.get('prescribed'))}, {escape_sql_string(item.get('administered'))}, {escape_sql_string(item.get('invoiced'))}, {escape_sql_string(item.get('discrepancy_type'))}, {item.get('unit_cost', 'NULL')}, {item.get('estimated_overbilled_amount', 'NULL')}, {escape_sql_string(item.get('observation'))}, {escape_sql_array(pages)})"
                values_list.append(val)
            sql.write(",\n".join(values_list))
            sql.write(";\n")

        sql.write("\nCOMMIT;\n")
        logger.info(f"Generated SQL at {output_file}")

if __name__ == "__main__":
    target_folder = "data/1619_69044_001"

    abs_folder = os.path.abspath(target_folder)
    output = "ingest_25966_141904403_144.sql"
    generate_sql(abs_folder, output)
