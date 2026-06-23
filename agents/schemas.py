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

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# --- Shared / SubAgent 1 Schemas ---

class MedicationItem(BaseModel):
    medication_name: str = Field(..., description="Medication Name (generic or commercial), preserving original naming.")
    presentation: str = Field(..., description="Presentation (mg, ml, comp, vial, amp, etc.)")
    amount: float = Field(..., description="Amount/Quantity")
    cost_per_unit: Optional[float] = Field(None, description="Cost per Unit")
    total_cost: float = Field(..., description="Total Cost. Use 0.0 if not found.")
    source_page: int = Field(..., description="Source Page Number")

class AfiliadoBillingData(BaseModel):
    afiliado_id: Optional[str] = Field(None, description="Affiliate ID / Credential Number")
    afiliado_name: Optional[str] = Field(None, description="Name of the affiliate/patient")
    afiliado_documento_identidad: Optional[str] = Field(None, description="Document/Identity Number")
    medications: List[MedicationItem]

class BillingExtractionResult(BaseModel):
    afiliados: List[AfiliadoBillingData]
    total_unique_medications: int = Field(..., description="Total number of unique medications extracted across all afiliados")

# --- Matching Agent Schemas ---

class ReducedMatchedItem(BaseModel):
    medication_name: str = Field(..., description="Medication Name from the input list.")
    presentation: str = Field(..., description="Presentation from the input list.")
    matched_droga_principal: Optional[str] = Field(None, description="Best match for Drug Generic node from graph.")
    matched_presentacion: Optional[str] = Field(None, description="Best match for Presentation from the graph.")
    match_score: Literal["EXACT", "PARTIAL", "NONE"] = Field(..., description="Matching confidence level")
    reasoning: Optional[str] = Field(None, description="Brief explanation of the choice.")

class MatchingResult(BaseModel):
    items: List[ReducedMatchedItem]


# --- SubAgent 2 Schemas ---

class ClinicalFinding(BaseModel):
    afiliado_name: str = Field(..., description="Name of the affiliate/patient (from billing)")
    medication_name: str = Field(..., description="Name of the medication being verified")
    found_in_prescriptions: bool = Field(..., description="Found in physician's order/indication")
    found_in_nursing_records: bool = Field(..., description="Found in nursing/administration records")
    administration_date: Optional[str] = Field(None, description="Date of administration of the drug (e.g., YYYY-MM-DD)")
    dose_freq_route: Optional[str] = Field(None, description="Dose, Frequency, Route summary")
    match_status: Literal["MATCH", "PARTIAL", "MISSING"]
    observation: Optional[str] = Field(None, description="Additional observations")
    pages: List[int] = Field(..., description="Pages where it was found")

class PageIssue(BaseModel):
    page: int
    issue: List[str]
    comment: Optional[str]

class UnparsedCandidate(BaseModel):
    billed_name: Optional[str]
    raw_line: str
    page: int
    reason: str

class SubAgent2Result(BaseModel):
    findings: List[ClinicalFinding]
    total_billed_reviewed: int
    count_match: int
    count_partial: int
    count_missing: int
    billed_not_found: List[str]
    pages_issues: List[PageIssue] = Field(default_factory=list)
    unparsed_candidates: List[UnparsedCandidate] = Field(default_factory=list)


# --- SubAgent 4 Schemas ---

class AuditDiscrepancy(BaseModel):
    afiliado_name: str = Field(..., description="Name of the affiliate/patient")
    medication: str
    prescribed: str
    administered: str
    administration_date: Optional[str] = Field(None, description="Date of administration of the drug extracted from clinical records")
    invoiced: str
    discrepancy_type: Literal["MATCH", "OVERBILLED", "NOT PRESCRIBED", "NOT ADMINISTERED"]
    unit_cost: Optional[float]
    estimated_overbilled_amount: float
    observation: Optional[str]
    pages: List[int]
    source: str

class SubAgent4Result(BaseModel):
    discrepancies: List[AuditDiscrepancy]
    total_invoiced_items: int
    percent_match: float
    percent_overbilled: float
    percent_not_prescribed: float
    percent_not_administered: float
    estimated_total_overbilling: float

# --- Consolidation Agent Schemas ---

class ReportFinding(BaseModel):
    category: str = Field(..., description="Category of the finding (e.g., Facturación, Verificación Clínica, Auditoría Económica)")
    description: str = Field(..., description="Detailed description of the finding in Spanish")
    impact: str = Field(..., description="Potential impact or recommendation in Spanish")

class ConsolidationReport(BaseModel):
    patient_name: str = Field(..., description="Name of the patient(s) involved in the audit. Comma separated if multiple.")
    executive_summary: str = Field(..., description="Executive summary of the entire audit case in Spanish. Must be formal and suitable for business users.")
    findings: List[ReportFinding] = Field(..., description="Key findings from the investigation")
    conclusion: str = Field(..., description="Final conclusion and structured recommendations for the auditors in Spanish")
