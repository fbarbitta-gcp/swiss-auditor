-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- Enable UUID extension if we want to use auto-generated UUIDs, 
-- though we might use the folder name (e.g., '1619_73677_011') as the primary key or a unique string.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Table: investigations
-- Represents a single folder / case processed by the pipeline.
CREATE TABLE investigations (
    id VARCHAR(255) PRIMARY KEY, -- Stores the Folder Name (e.g., "1619_73677_011")
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Indice ByTree por fecha descendente.
    status VARCHAR(50) DEFAULT 'processed', -- Indice ByTree por estado.
    -- Aggregate Data from Economic Audit Result
    total_invoiced_items INT, 
    percent_match NUMERIC(5, 2),
    percent_overbilled NUMERIC(5, 2), 
    percent_not_prescribed NUMERIC(5, 2), 
    percent_not_administered NUMERIC(5, 2), 
    estimated_total_overbilling NUMERIC(18, 2), -- Indice descendente.
    trace_id TEXT,
    token_usage JSONB
);

-- Table: billing_items
-- Extracted line items from the invoice (Step 1).
CREATE TABLE billing_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id VARCHAR(255) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    afiliado_id TEXT,
    afiliado_name TEXT,
    afiliado_documento_identidad TEXT,
    medication_name TEXT, -- Indice gin
    presentation TEXT,
    amount NUMERIC(18, 2),
    cost_per_unit NUMERIC(18, 2),
    total_cost NUMERIC(18, 2), -- Indice descendente, por las dudas se podria quitar toca validar.
    source_page INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: audit_discrepancies
-- Findings from the Economic Audit Agent (Step 3).
CREATE TABLE audit_discrepancies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id VARCHAR(255) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    medication_name TEXT, -- Inidice gin
    prescribed_text TEXT,
    administered_text TEXT,
    administration_date TEXT,
    invoiced_text TEXT,
    discrepancy_type VARCHAR(100), -- ByTree
    unit_cost NUMERIC(18, 2),
    estimated_overbilled_amount NUMERIC(18, 2), -- Indice descendente.
    observation TEXT,
    source_pages INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- Indice ByTree por fecha descendente.
);


-- Table: prestadores
-- Provider-specific rules for identifying invoices.
CREATE TABLE prestadores (
    id_prestador VARCHAR(50) PRIMARY KEY,
    keywords TEXT -- Comma-separated keywords
);

-- Index for faster lookups by investigation
CREATE INDEX idx_billing_items_inv_id ON billing_items(investigation_id);
CREATE INDEX idx_audit_discrepancies_inv_id ON audit_discrepancies(investigation_id);

-- Additional indexes based on comments/usage
-- Investigations Indexes
CREATE INDEX idx_investigations_status ON investigations(status);
CREATE INDEX idx_investigations_processed_at ON investigations(processed_at DESC);
CREATE INDEX idx_investigations_overbilling ON investigations(estimated_total_overbilling DESC);

-- Billing Items Indexes
CREATE INDEX idx_billing_items_medication_gin ON billing_items USING gin (medication_name gin_trgm_ops);
CREATE INDEX idx_billing_items_total_cost ON billing_items(total_cost DESC);

-- Audit Discrepancies Indexes
CREATE INDEX idx_audit_discrepancies_type ON audit_discrepancies(discrepancy_type);
CREATE INDEX idx_audit_discrepancies_medication_gin ON audit_discrepancies USING gin (medication_name gin_trgm_ops);
CREATE INDEX idx_audit_discrepancies_overbilled ON audit_discrepancies(estimated_overbilled_amount DESC);
CREATE INDEX idx_audit_discrepancies_created_at ON audit_discrepancies(created_at DESC);


