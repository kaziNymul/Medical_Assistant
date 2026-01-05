"""Tests for data models."""

import pytest
from datetime import datetime

from src.models.schemas import (
    ClinicalDocument,
    ClinicalExtraction,
    DataCompleteness,
    DocumentChunk,
    Evidence,
    HbA1cTrend,
    QueryRequest,
    QueryResponse,
    SmokingStatus,
    SourceType,
)


class TestClinicalExtraction:
    """Test cases for ClinicalExtraction model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        extraction = ClinicalExtraction()
        
        assert extraction.primary_diagnosis is None
        assert extraction.latest_hba1c is None
        assert extraction.medications == []
        assert extraction.data_completeness == DataCompleteness.MISSING
        assert extraction.confidence_score == 0.0
        assert extraction.pii_detected is False
    
    def test_full_extraction(self):
        """Test creating a complete extraction."""
        extraction = ClinicalExtraction(
            primary_diagnosis="Type 2 Diabetes Mellitus",
            latest_hba1c="7.5%",
            hba1c_trend=HbA1cTrend.IMPROVING,
            medications=["Metformin", "Glipizide"],
            smoking_status=SmokingStatus.FORMER_SMOKER,
            complications=["Neuropathy"],
            data_completeness=DataCompleteness.COMPLETE,
            confidence_score=0.85,
            evidence=[
                Evidence(
                    field="primary_diagnosis",
                    quote="Diagnosis: Type 2 Diabetes",
                    confidence=0.9,
                )
            ],
            clinical_explanation="Patient has well-controlled diabetes.",
        )
        
        assert extraction.primary_diagnosis == "Type 2 Diabetes Mellitus"
        assert len(extraction.medications) == 2
        assert extraction.confidence_score == 0.85
    
    def test_confidence_validation(self):
        """Test that confidence score is validated."""
        with pytest.raises(ValueError):
            ClinicalExtraction(confidence_score=1.5)
        
        with pytest.raises(ValueError):
            ClinicalExtraction(confidence_score=-0.1)


class TestEvidence:
    """Test cases for Evidence model."""
    
    def test_evidence_creation(self):
        """Test creating evidence."""
        evidence = Evidence(
            field="latest_hba1c",
            quote="HbA1c: 7.2%",
            source_type=SourceType.LAB_RESULT,
            date="2025-12-15",
            confidence=0.95,
        )
        
        assert evidence.field == "latest_hba1c"
        assert evidence.confidence == 0.95


class TestDocumentChunk:
    """Test cases for DocumentChunk model."""
    
    def test_chunk_creation(self):
        """Test creating a document chunk."""
        chunk = DocumentChunk(
            chunk_id="DOC-123-C0001",
            document_id="DOC-123",
            patient_id="P12345678901",
            content="Clinical note content here.",
            source_type=SourceType.DISCHARGE_SUMMARY,
            chunk_index=0,
            total_chunks=3,
        )
        
        assert chunk.chunk_id == "DOC-123-C0001"
        assert chunk.chunk_index == 0
        assert chunk.total_chunks == 3


class TestQueryModels:
    """Test cases for query request/response models."""
    
    def test_query_request_defaults(self):
        """Test query request default values."""
        request = QueryRequest(query="What is the patient's HbA1c?")
        
        assert request.query == "What is the patient's HbA1c?"
        assert request.patient_id is None
        assert request.top_k == 5
        assert request.include_evidence is True
    
    def test_query_request_validation(self):
        """Test query request validation."""
        request = QueryRequest(query="test", top_k=10)
        assert request.top_k == 10
        
        with pytest.raises(ValueError):
            QueryRequest(query="test", top_k=25)  # Max is 20


class TestEnums:
    """Test cases for enum values."""
    
    def test_source_types(self):
        """Test source type enum values."""
        assert SourceType.DISCHARGE_SUMMARY.value == "discharge_summary"
        assert SourceType.PROGRESS_NOTE.value == "progress_note"
        assert SourceType.LAB_RESULT.value == "lab_result"
    
    def test_smoking_status(self):
        """Test smoking status enum values."""
        assert SmokingStatus.CURRENT_SMOKER.value == "current_smoker"
        assert SmokingStatus.NEVER_SMOKED.value == "never_smoked"
    
    def test_hba1c_trend(self):
        """Test HbA1c trend enum values."""
        assert HbA1cTrend.IMPROVING.value == "improving"
        assert HbA1cTrend.WORSENING.value == "worsening"
