"""
Agent state definitions for LangGraph workflow.

Defines the shared state that flows through the agent pipeline.
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field

from src.models.schemas import (
    ClinicalExtraction,
    DataCompleteness,
    DocumentChunk,
    Evidence,
    HbA1cTrend,
    SmokingStatus,
)


class AgentState(BaseModel):
    """
    Shared state for the clinical extraction workflow.
    
    This state is passed between agents in the LangGraph pipeline.
    """
    
    # Input
    query: str = Field(..., description="The original query or extraction request")
    patient_id: Optional[str] = Field(None, description="Patient ID filter")
    
    # Retrieved context
    retrieved_chunks: list[DocumentChunk] = Field(
        default_factory=list,
        description="Chunks retrieved from vector store"
    )
    context: str = Field(default="", description="Combined context text")
    
    # Extraction results
    extraction: Optional[ClinicalExtraction] = Field(
        None,
        description="Extracted clinical information"
    )
    
    # Intermediate results
    raw_extraction: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw extraction before validation"
    )
    
    # Validation
    is_valid: bool = Field(default=False, description="Whether extraction passed validation")
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Validation error messages"
    )
    
    # Explanation
    explanation: str = Field(default="", description="Human-readable explanation")
    
    # Metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    processing_time_ms: float = Field(default=0.0)
    
    # Error handling
    error: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class ExtractionResult(BaseModel):
    """
    Result from the extraction agent.
    
    Used for intermediate processing before final validation.
    """
    
    primary_diagnosis: Optional[str] = None
    latest_hba1c: Optional[str] = None
    hba1c_trend: Optional[str] = None
    medications: list[str] = Field(default_factory=list)
    smoking_status: Optional[str] = None
    complications: list[str] = Field(default_factory=list)
    
    # Evidence for each field
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    
    # Confidence per field
    field_confidences: dict[str, float] = Field(default_factory=dict)
    
    def to_clinical_extraction(self) -> ClinicalExtraction:
        """Convert to the final ClinicalExtraction format."""
        # Convert string enums
        hba1c_trend = None
        if self.hba1c_trend:
            try:
                hba1c_trend = HbA1cTrend(self.hba1c_trend.lower())
            except ValueError:
                hba1c_trend = HbA1cTrend.UNKNOWN
        
        smoking_status = None
        if self.smoking_status:
            try:
                smoking_status = SmokingStatus(self.smoking_status.lower().replace(" ", "_"))
            except ValueError:
                smoking_status = SmokingStatus.UNKNOWN
        
        # Determine data completeness
        filled_fields = sum([
            1 for v in [
                self.primary_diagnosis,
                self.latest_hba1c,
                self.medications,
                self.smoking_status,
            ] if v
        ])
        
        if filled_fields >= 3:
            completeness = DataCompleteness.COMPLETE
        elif filled_fields >= 1:
            completeness = DataCompleteness.PARTIAL
        else:
            completeness = DataCompleteness.MISSING
        
        # Calculate overall confidence
        if self.field_confidences:
            avg_confidence = sum(self.field_confidences.values()) / len(self.field_confidences)
        else:
            avg_confidence = 0.5 if filled_fields > 0 else 0.0
        
        # Convert evidence
        evidence_list = [
            Evidence(
                field=e.get("field", ""),
                quote=e.get("quote", ""),
                source_type=e.get("source_type", "unknown"),
                date=e.get("date"),
                confidence=e.get("confidence", 0.5),
            )
            for e in self.evidence_items
        ]
        
        return ClinicalExtraction(
            primary_diagnosis=self.primary_diagnosis,
            latest_hba1c=self.latest_hba1c,
            hba1c_trend=hba1c_trend,
            medications=self.medications,
            smoking_status=smoking_status,
            complications=self.complications,
            data_completeness=completeness,
            confidence_score=avg_confidence,
            evidence=evidence_list,
            pii_detected=False,  # Should be masked already
        )
