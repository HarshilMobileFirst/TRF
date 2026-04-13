from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ValidationStatus = Literal["valid", "review_required", "invalid"]
DocumentStatus = Literal["processed", "corrected", "approved"]


class ExtractedData(BaseModel):
    patient_name: str | None = None
    patient_id: str | None = None
    age: int | None = None
    gender: str | None = None
    doctor_name: str | None = None
    hospital_or_center_name: str | None = None
    requisition_date: str | None = None
    sample_type: str | None = None
    test_names: list[str] = Field(default_factory=list)
    test_codes: list[str] = Field(default_factory=list)
    priority: str | None = None
    contact_number: str | None = None
    notes: str | None = None


class ConfidenceScores(BaseModel):
    patient_name: float = 0.0
    patient_id: float = 0.0
    age: float = 0.0
    gender: float = 0.0
    doctor_name: float = 0.0
    hospital_or_center_name: float = 0.0
    requisition_date: float = 0.0
    sample_type: float = 0.0
    test_names: float = 0.0
    test_codes: float = 0.0
    priority: float = 0.0
    contact_number: float = 0.0
    notes: float = 0.0
    extraction_confidence: float = 0.0


class ValidationResult(BaseModel):
    status: ValidationStatus = "review_required"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TRFDocument(BaseModel):
    document_id: str
    status: DocumentStatus = "processed"
    source_file_name: str
    extraction_provider: str = "openai"
    extraction_model: str | None = None
    extraction_note: str | None = None
    extracted_data: ExtractedData
    confidence: ConfidenceScores
    validation: ValidationResult
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None
    ocr_text: str | None = None


class TRFListItem(BaseModel):
    document_id: str
    status: DocumentStatus
    source_file_name: str
    patient_name: str | None = None
    patient_id: str | None = None
    requisition_date: str | None = None
    validation_status: ValidationStatus
    updated_at: datetime


class CorrectionPayload(BaseModel):
    extracted_data: ExtractedData
