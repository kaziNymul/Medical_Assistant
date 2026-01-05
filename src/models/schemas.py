"""
Data models for the Medical Assistant.

These Pydantic models define the structure for:
- Clinical documents
- Extraction outputs
- Evidence citations
- API requests/responses
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DataCompleteness(str, Enum):
    """Enum for data completeness status."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class SourceType(str, Enum):
    """Types of clinical document sources."""
    DISCHARGE_SUMMARY = "discharge_summary"
    PROGRESS_NOTE = "progress_note"
    LAB_RESULT = "lab_result"
    RADIOLOGY_REPORT = "radiology_report"
    PRESCRIPTION = "prescription"
    CONSULTATION = "consultation"
    ADMISSION_NOTE = "admission_note"
    UNKNOWN = "unknown"


class SmokingStatus(str, Enum):
    """Smoking status enumeration."""
    CURRENT_SMOKER = "current_smoker"
    FORMER_SMOKER = "former_smoker"
    NEVER_SMOKED = "never_smoked"
    UNKNOWN = "unknown"


class HbA1cTrend(str, Enum):
    """HbA1c trend direction."""
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    """
    Evidence citation for extracted information.
    
    Each extracted field should have supporting evidence
    that points back to the source text.
    """
    field: str = Field(..., description="The field this evidence supports")
    quote: str = Field(..., description="Direct quote from source text")
    source_type: SourceType = Field(default=SourceType.UNKNOWN)
    date: Optional[str] = Field(None, description="Date of the source document")
    chunk_id: Optional[str] = Field(None, description="ID of the source chunk")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ClinicalExtraction(BaseModel):
    """
    Master JSON output contract for clinical extractions.
    
    This is the standard output format that all extraction
    agents must produce. Follows the contract defined in README.
    """
    # Primary clinical fields
    primary_diagnosis: Optional[str] = Field(
        None, 
        description="Primary diagnosis from clinical notes"
    )
    latest_hba1c: Optional[str] = Field(
        None, 
        description="Most recent HbA1c value with units"
    )
    hba1c_trend: Optional[HbA1cTrend] = Field(
        None, 
        description="Trend direction of HbA1c values"
    )
    medications: list[str] = Field(
        default_factory=list, 
        description="List of current medications"
    )
    smoking_status: Optional[SmokingStatus] = Field(
        None, 
        description="Patient smoking status"
    )
    complications: list[str] = Field(
        default_factory=list, 
        description="List of complications or comorbidities"
    )
    
    # Metadata fields
    data_completeness: DataCompleteness = Field(
        default=DataCompleteness.MISSING,
        description="Assessment of data completeness"
    )
    confidence_score: float = Field(
        default=0.0, 
        ge=0.0, 
        le=1.0,
        description="Overall confidence in extraction"
    )
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Evidence citations for extracted fields"
    )
    clinical_explanation: Optional[str] = Field(
        None,
        description="Human-readable explanation of findings"
    )
    pii_detected: bool = Field(
        default=False,
        description="Whether PII was detected in source"
    )
    
    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(default="phase1-local")


class ClinicalDocument(BaseModel):
    """
    Represents a clinical document for processing.
    """
    document_id: str = Field(..., description="Unique document identifier")
    patient_id: str = Field(..., description="Pseudonymized patient ID")
    episode_id: Optional[str] = Field(None, description="Episode/encounter ID")
    source_type: SourceType = Field(default=SourceType.UNKNOWN)
    content: str = Field(..., description="Document text content")
    date: Optional[str] = Field(None, description="Document date")
    is_masked: bool = Field(default=False, description="Whether PII has been masked")
    metadata: dict = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """
    A chunk of a clinical document for RAG.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    patient_id: str = Field(..., description="Pseudonymized patient ID")
    content: str = Field(..., description="Chunk text content")
    source_type: SourceType = Field(default=SourceType.UNKNOWN)
    chunk_index: int = Field(..., description="Position in document")
    total_chunks: int = Field(..., description="Total chunks in document")
    metadata: dict = Field(default_factory=dict)


class QueryRequest(BaseModel):
    """API request for querying clinical documents."""
    query: str = Field(..., description="Natural language query")
    patient_id: Optional[str] = Field(None, description="Filter by patient ID")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")
    include_evidence: bool = Field(default=True)


class QueryResponse(BaseModel):
    """API response for clinical queries."""
    query: str
    extraction: ClinicalExtraction
    retrieved_chunks: list[DocumentChunk] = Field(default_factory=list)
    processing_time_ms: float = Field(default=0.0)


class DocumentUploadRequest(BaseModel):
    """Request to upload and process a clinical document."""
    content: str = Field(..., description="Document text content")
    patient_id: str = Field(..., description="Patient identifier (will be pseudonymized)")
    source_type: SourceType = Field(default=SourceType.UNKNOWN)
    document_date: Optional[str] = Field(None)


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str
    chunks_created: int
    is_masked: bool
    pii_items_masked: int = Field(default=0)
    message: str


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "0.1.0"
    environment: str = "development"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
