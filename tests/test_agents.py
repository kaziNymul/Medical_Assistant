"""Tests for the agent workflow."""

import pytest

from src.agents.state import AgentState, ExtractionResult
from src.agents.nodes import ExtractionAgent, ValidationAgent, ExplanationAgent
from src.models.schemas import HbA1cTrend, SmokingStatus, DataCompleteness


class TestAgentState:
    """Test cases for AgentState."""
    
    def test_initial_state(self):
        """Test creating an initial state."""
        state = AgentState(query="What is the HbA1c?")
        
        assert state.query == "What is the HbA1c?"
        assert state.patient_id is None
        assert state.retrieved_chunks == []
        assert state.extraction is None
        assert state.is_valid is False
    
    def test_state_with_context(self):
        """Test state with context."""
        state = AgentState(
            query="Extract clinical data",
            patient_id="P12345678901",
            context="HbA1c: 7.5%. Patient on Metformin.",
        )
        
        assert len(state.context) > 0


class TestExtractionResult:
    """Test cases for ExtractionResult."""
    
    def test_to_clinical_extraction(self):
        """Test converting to ClinicalExtraction."""
        result = ExtractionResult(
            primary_diagnosis="Type 2 Diabetes",
            latest_hba1c="7.5%",
            hba1c_trend="improving",
            medications=["Metformin", "Glipizide"],
            smoking_status="never_smoked",
            complications=["Neuropathy"],
            field_confidences={
                "primary_diagnosis": 0.9,
                "latest_hba1c": 0.95,
            },
        )
        
        extraction = result.to_clinical_extraction()
        
        assert extraction.primary_diagnosis == "Type 2 Diabetes"
        assert extraction.latest_hba1c == "7.5%"
        assert extraction.hba1c_trend == HbA1cTrend.IMPROVING
        assert extraction.smoking_status == SmokingStatus.NEVER_SMOKED
        assert len(extraction.medications) == 2
        assert extraction.data_completeness == DataCompleteness.COMPLETE


class TestExtractionAgent:
    """Test cases for ExtractionAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create an extraction agent."""
        return ExtractionAgent()
    
    def test_extract_hba1c(self, agent):
        """Test extracting HbA1c from context."""
        state = AgentState(
            query="Extract HbA1c",
            context="Patient's HbA1c: 8.5%. Previous HbA1c was 9.2%.",
        )
        
        result = agent.run(state)
        
        assert result.raw_extraction.get("latest_hba1c") == "8.5%"
        assert result.raw_extraction.get("hba1c_trend") == "improving"
    
    def test_extract_medications(self, agent):
        """Test extracting medications from context."""
        state = AgentState(
            query="Extract medications",
            context="Current medications: Metformin 1000mg, Lisinopril 10mg, Atorvastatin 20mg",
        )
        
        result = agent.run(state)
        
        meds = result.raw_extraction.get("medications", [])
        assert "Metformin" in meds
        assert "Lisinopril" in meds
        assert "Atorvastatin" in meds
    
    def test_extract_smoking_status(self, agent):
        """Test extracting smoking status."""
        state = AgentState(
            query="Extract smoking status",
            context="Social history: Former smoker, quit 5 years ago.",
        )
        
        result = agent.run(state)
        
        assert result.raw_extraction.get("smoking_status") == "former_smoker"
    
    def test_extract_empty_context(self, agent):
        """Test extraction with empty context."""
        state = AgentState(query="Extract data", context="")
        
        result = agent.run(state)
        
        assert result.raw_extraction == {}


class TestValidationAgent:
    """Test cases for ValidationAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a validation agent."""
        return ValidationAgent()
    
    def test_valid_extraction(self, agent):
        """Test validating a correct extraction."""
        state = AgentState(
            query="Validate",
            raw_extraction={
                "primary_diagnosis": "Type 2 Diabetes",
                "latest_hba1c": "7.5%",
                "smoking_status": "never_smoked",
            },
        )
        
        result = agent.run(state)
        
        assert result.is_valid is True
        assert result.validation_errors == []
    
    def test_invalid_hba1c_range(self, agent):
        """Test detecting invalid HbA1c range."""
        state = AgentState(
            query="Validate",
            raw_extraction={
                "latest_hba1c": "25.0%",  # Invalid - too high
            },
        )
        
        result = agent.run(state)
        
        assert result.is_valid is False
        assert any("range" in e.lower() for e in result.validation_errors)
    
    def test_empty_extraction(self, agent):
        """Test validating empty extraction."""
        state = AgentState(query="Validate", raw_extraction={})
        
        result = agent.run(state)
        
        assert result.is_valid is False


class TestExplanationAgent:
    """Test cases for ExplanationAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create an explanation agent."""
        return ExplanationAgent()
    
    def test_generate_explanation(self, agent):
        """Test generating an explanation."""
        state = AgentState(
            query="Explain",
            is_valid=True,
            raw_extraction={
                "primary_diagnosis": "Type 2 Diabetes",
                "latest_hba1c": "7.5%",
                "hba1c_trend": "improving",
                "medications": ["Metformin", "Glipizide"],
                "smoking_status": "former_smoker",
            },
        )
        
        result = agent.run(state)
        
        assert len(result.explanation) > 0
        assert "Type 2 Diabetes" in result.explanation
        assert "7.5%" in result.explanation
        assert result.extraction is not None
    
    def test_explanation_with_validation_errors(self, agent):
        """Test explanation includes validation warnings."""
        state = AgentState(
            query="Explain",
            is_valid=False,
            validation_errors=["Invalid HbA1c value"],
            raw_extraction={"latest_hba1c": "25%"},
        )
        
        result = agent.run(state)
        
        assert "⚠️" in result.explanation or "Validation" in result.explanation
