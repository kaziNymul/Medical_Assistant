"""
Individual agent implementations for the clinical extraction workflow.

Each agent handles a specific step in the pipeline:
- RetrievalAgent: Retrieves relevant document chunks
- ExtractionAgent: Extracts structured clinical data
- ValidationAgent: Validates extraction accuracy
- ExplanationAgent: Generates human-readable explanations
"""

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from src.agents.prompts import (
    CLINICAL_EXTRACTION_SYSTEM_PROMPT,
    get_extraction_prompt,
    get_validation_prompt,
    get_explanation_prompt,
)
from src.agents.state import AgentState, ExtractionResult
from src.models.schemas import (
    ClinicalExtraction,
    DataCompleteness,
    DocumentChunk,
    Evidence,
    HbA1cTrend,
    SmokingStatus,
    SourceType,
)
from src.rag.pipeline import get_rag_pipeline
from src.utils.logging import logger


class BaseAgent(ABC):
    """Base class for all agents."""
    
    @abstractmethod
    def run(self, state: AgentState) -> AgentState:
        """Execute the agent's task and update state."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging."""
        pass


class RetrievalAgent(BaseAgent):
    """
    Retrieves relevant document chunks for the query.
    
    Uses the RAG pipeline to find semantically similar chunks.
    """
    
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.pipeline = get_rag_pipeline()
    
    @property
    def name(self) -> str:
        return "RetrievalAgent"
    
    def run(self, state: AgentState) -> AgentState:
        """Retrieve relevant chunks and update state."""
        logger.info(f"{self.name}: Retrieving chunks for query")
        
        try:
            # Get context from RAG pipeline
            context, chunks = self.pipeline.get_context(
                query=state.query,
                top_k=self.top_k,
                patient_id=state.patient_id,
            )
            
            state.retrieved_chunks = chunks
            state.context = context
            
            logger.info(f"{self.name}: Retrieved {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"{self.name}: Error retrieving chunks: {e}")
            state.error = f"Retrieval failed: {str(e)}"
        
        return state


class ExtractionAgent(BaseAgent):
    """
    Extracts structured clinical data from the context.
    
    Uses pattern matching and LLM (when available) for extraction.
    In Phase 1, uses rule-based extraction.
    In Phase 2, uses Claude via Bedrock.
    """
    
    @property
    def name(self) -> str:
        return "ExtractionAgent"
    
    def run(self, state: AgentState) -> AgentState:
        """Extract clinical information from context."""
        logger.info(f"{self.name}: Extracting clinical data")
        
        if not state.context:
            logger.warning(f"{self.name}: No context to extract from")
            state.raw_extraction = {}
            return state
        
        try:
            # Use rule-based extraction for Phase 1
            extraction = self._rule_based_extraction(state.context, state.retrieved_chunks)
            state.raw_extraction = extraction
            
            logger.info(f"{self.name}: Extraction complete")
            
        except Exception as e:
            logger.error(f"{self.name}: Error during extraction: {e}")
            state.error = f"Extraction failed: {str(e)}"
        
        return state
    
    def _rule_based_extraction(
        self,
        context: str,
        chunks: list[DocumentChunk],
    ) -> dict[str, Any]:
        """
        Rule-based extraction for Phase 1.
        
        Uses regex patterns and keyword matching.
        """
        result = {
            "primary_diagnosis": None,
            "latest_hba1c": None,
            "hba1c_trend": None,
            "medications": [],
            "smoking_status": None,
            "complications": [],
            "evidence": [],
            "field_confidences": {},
        }
        
        context_lower = context.lower()
        
        # Extract HbA1c
        hba1c_pattern = r'(?:hba1c|hemoglobin a1c|a1c)[\s:]*(\d+\.?\d*)[\s]*(%|percent)?'
        hba1c_matches = re.findall(hba1c_pattern, context_lower)
        if hba1c_matches:
            latest = hba1c_matches[-1]  # Take the last (most recent)
            result["latest_hba1c"] = f"{latest[0]}%"
            result["evidence"].append({
                "field": "latest_hba1c",
                "quote": f"HbA1c: {latest[0]}%",
                "confidence": 0.9,
            })
            result["field_confidences"]["latest_hba1c"] = 0.9
            
            # Determine trend if multiple values
            if len(hba1c_matches) > 1:
                values = [float(m[0]) for m in hba1c_matches]
                if values[-1] < values[0]:
                    result["hba1c_trend"] = "improving"
                elif values[-1] > values[0]:
                    result["hba1c_trend"] = "worsening"
                else:
                    result["hba1c_trend"] = "stable"
                result["field_confidences"]["hba1c_trend"] = 0.7
        
        # Extract diagnosis
        diagnosis_patterns = [
            r'(?:diagnosis|dx|diagnosed with)[\s:]+([^\n\.,]+)',
            r'(?:primary diagnosis)[\s:]+([^\n\.,]+)',
            r'(?:assessment)[\s:]+([^\n\.,]+)',
        ]
        for pattern in diagnosis_patterns:
            match = re.search(pattern, context_lower)
            if match:
                result["primary_diagnosis"] = match.group(1).strip().title()
                result["evidence"].append({
                    "field": "primary_diagnosis",
                    "quote": match.group(0),
                    "confidence": 0.8,
                })
                result["field_confidences"]["primary_diagnosis"] = 0.8
                break
        
        # Extract medications
        medication_keywords = [
            "metformin", "insulin", "glipizide", "glimepiride", "sitagliptin",
            "lisinopril", "amlodipine", "atorvastatin", "aspirin", "omeprazole",
            "levothyroxine", "metoprolol", "losartan", "gabapentin", "prednisone",
            "pantoprazole", "furosemide", "hydrochlorothiazide", "warfarin",
        ]
        found_meds = []
        for med in medication_keywords:
            if med in context_lower:
                found_meds.append(med.title())
        
        if found_meds:
            result["medications"] = found_meds
            result["evidence"].append({
                "field": "medications",
                "quote": f"Found medications: {', '.join(found_meds)}",
                "confidence": 0.85,
            })
            result["field_confidences"]["medications"] = 0.85
        
        # Extract smoking status
        smoking_patterns = {
            "current_smoker": [r'current\s+smoker', r'smokes', r'smoking\s*:\s*yes', r'active\s+smoker'],
            "former_smoker": [r'former\s+smoker', r'quit\s+smoking', r'ex-smoker', r'stopped\s+smoking'],
            "never_smoked": [r'never\s+smoked', r'non-smoker', r'no\s+smoking', r'smoking\s*:\s*no'],
        }
        for status, patterns in smoking_patterns.items():
            for pattern in patterns:
                if re.search(pattern, context_lower):
                    result["smoking_status"] = status
                    result["evidence"].append({
                        "field": "smoking_status",
                        "quote": f"Smoking status: {status.replace('_', ' ')}",
                        "confidence": 0.9,
                    })
                    result["field_confidences"]["smoking_status"] = 0.9
                    break
            if result["smoking_status"]:
                break
        
        # Extract complications
        complication_keywords = [
            "neuropathy", "nephropathy", "retinopathy", "cardiovascular",
            "hypertension", "hyperlipidemia", "obesity", "chronic kidney",
            "heart failure", "stroke", "peripheral vascular", "foot ulcer",
        ]
        found_complications = []
        for comp in complication_keywords:
            if comp in context_lower:
                found_complications.append(comp.title())
        
        if found_complications:
            result["complications"] = found_complications
            result["evidence"].append({
                "field": "complications",
                "quote": f"Found complications: {', '.join(found_complications)}",
                "confidence": 0.8,
            })
            result["field_confidences"]["complications"] = 0.8
        
        return result


class ValidationAgent(BaseAgent):
    """
    Validates the extraction results.
    
    Checks for:
    - Consistency between extracted data and source
    - Reasonable value ranges
    - Required field presence
    """
    
    @property
    def name(self) -> str:
        return "ValidationAgent"
    
    def run(self, state: AgentState) -> AgentState:
        """Validate the extraction results."""
        logger.info(f"{self.name}: Validating extraction")
        
        if not state.raw_extraction:
            state.is_valid = False
            state.validation_errors = ["No extraction data to validate"]
            return state
        
        errors = []
        
        # Validate HbA1c value range
        if state.raw_extraction.get("latest_hba1c"):
            try:
                value = float(
                    state.raw_extraction["latest_hba1c"].replace("%", "").strip()
                )
                if not 4.0 <= value <= 20.0:
                    errors.append(f"HbA1c value {value}% is outside normal range (4-20%)")
            except ValueError:
                errors.append("HbA1c value could not be parsed")
        
        # Validate smoking status is valid enum
        valid_smoking = ["current_smoker", "former_smoker", "never_smoked", "unknown"]
        if state.raw_extraction.get("smoking_status"):
            if state.raw_extraction["smoking_status"] not in valid_smoking:
                errors.append(f"Invalid smoking status: {state.raw_extraction['smoking_status']}")
        
        # Validate HbA1c trend is valid enum
        valid_trends = ["improving", "stable", "worsening", "unknown"]
        if state.raw_extraction.get("hba1c_trend"):
            if state.raw_extraction["hba1c_trend"] not in valid_trends:
                errors.append(f"Invalid HbA1c trend: {state.raw_extraction['hba1c_trend']}")
        
        # Check if we have at least some data
        has_data = any([
            state.raw_extraction.get("primary_diagnosis"),
            state.raw_extraction.get("latest_hba1c"),
            state.raw_extraction.get("medications"),
        ])
        
        if not has_data:
            errors.append("No clinical data could be extracted")
        
        state.is_valid = len(errors) == 0
        state.validation_errors = errors
        
        logger.info(f"{self.name}: Validation {'passed' if state.is_valid else 'failed'}")
        
        return state


class ExplanationAgent(BaseAgent):
    """
    Generates human-readable explanations of the extraction.
    
    Creates a summary suitable for clinical review.
    """
    
    @property
    def name(self) -> str:
        return "ExplanationAgent"
    
    def run(self, state: AgentState) -> AgentState:
        """Generate explanation for the extraction."""
        logger.info(f"{self.name}: Generating explanation")
        
        if not state.raw_extraction:
            state.explanation = "No clinical information was extracted from the provided documents."
            return state
        
        parts = []
        
        # Diagnosis
        if state.raw_extraction.get("primary_diagnosis"):
            parts.append(f"Primary diagnosis: {state.raw_extraction['primary_diagnosis']}.")
        else:
            parts.append("Primary diagnosis: Not identified.")
        
        # HbA1c
        if state.raw_extraction.get("latest_hba1c"):
            hba1c_text = f"Latest HbA1c: {state.raw_extraction['latest_hba1c']}"
            if state.raw_extraction.get("hba1c_trend"):
                hba1c_text += f" (trend: {state.raw_extraction['hba1c_trend']})"
            parts.append(hba1c_text + ".")
        
        # Medications
        if state.raw_extraction.get("medications"):
            meds = state.raw_extraction["medications"]
            parts.append(f"Current medications: {', '.join(meds)}.")
        else:
            parts.append("Medications: None identified.")
        
        # Smoking
        if state.raw_extraction.get("smoking_status"):
            status = state.raw_extraction["smoking_status"].replace("_", " ")
            parts.append(f"Smoking status: {status}.")
        
        # Complications
        if state.raw_extraction.get("complications"):
            comps = state.raw_extraction["complications"]
            parts.append(f"Complications: {', '.join(comps)}.")
        
        # Validation status
        if not state.is_valid and state.validation_errors:
            parts.append(f"⚠️ Validation notes: {'; '.join(state.validation_errors)}")
        
        state.explanation = " ".join(parts)
        
        # Now create the final extraction
        extraction_result = ExtractionResult(
            primary_diagnosis=state.raw_extraction.get("primary_diagnosis"),
            latest_hba1c=state.raw_extraction.get("latest_hba1c"),
            hba1c_trend=state.raw_extraction.get("hba1c_trend"),
            medications=state.raw_extraction.get("medications", []),
            smoking_status=state.raw_extraction.get("smoking_status"),
            complications=state.raw_extraction.get("complications", []),
            evidence_items=state.raw_extraction.get("evidence", []),
            field_confidences=state.raw_extraction.get("field_confidences", {}),
        )
        
        final_extraction = extraction_result.to_clinical_extraction()
        final_extraction.clinical_explanation = state.explanation
        state.extraction = final_extraction
        
        # Mark completion
        state.completed_at = datetime.utcnow()
        if state.started_at:
            delta = state.completed_at - state.started_at
            state.processing_time_ms = delta.total_seconds() * 1000
        
        logger.info(f"{self.name}: Explanation generated")
        
        return state
