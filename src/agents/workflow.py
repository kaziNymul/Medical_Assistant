"""
LangGraph workflow for clinical extraction.

Orchestrates the agent pipeline:
RetrievalAgent → ExtractionAgent → ValidationAgent → ExplanationAgent
"""

from typing import Any, Optional

from src.agents.nodes import (
    RetrievalAgent,
    ExtractionAgent,
    ValidationAgent,
    ExplanationAgent,
)
from src.agents.state import AgentState
from src.models.schemas import ClinicalExtraction, QueryResponse
from src.utils.logging import logger


class ClinicalExtractionWorkflow:
    """
    LangGraph-style workflow for clinical extraction.
    
    This is a simplified implementation that can be upgraded
    to use LangGraph's StateGraph in Phase 2.
    """
    
    def __init__(self, top_k: int = 5):
        """
        Initialize the workflow.
        
        Args:
            top_k: Number of chunks to retrieve.
        """
        self.retrieval_agent = RetrievalAgent(top_k=top_k)
        self.extraction_agent = ExtractionAgent()
        self.validation_agent = ValidationAgent()
        self.explanation_agent = ExplanationAgent()
    
    def run(
        self,
        query: str,
        patient_id: str | None = None,
    ) -> AgentState:
        """
        Run the full extraction workflow.
        
        Args:
            query: The query or extraction request.
            patient_id: Optional patient ID filter.
            
        Returns:
            Final AgentState with extraction results.
        """
        logger.info("Starting clinical extraction workflow")
        
        # Initialize state
        state = AgentState(query=query, patient_id=patient_id)
        
        # Run pipeline
        state = self.retrieval_agent.run(state)
        if state.error:
            logger.error(f"Workflow failed at retrieval: {state.error}")
            return state
        
        state = self.extraction_agent.run(state)
        if state.error:
            logger.error(f"Workflow failed at extraction: {state.error}")
            return state
        
        state = self.validation_agent.run(state)
        # Continue even if validation has errors
        
        state = self.explanation_agent.run(state)
        
        logger.info(
            f"Workflow completed in {state.processing_time_ms:.1f}ms | "
            f"Valid: {state.is_valid}"
        )
        
        return state
    
    def extract(
        self,
        query: str,
        patient_id: str | None = None,
    ) -> QueryResponse:
        """
        Convenience method that returns a QueryResponse.
        
        Args:
            query: The query or extraction request.
            patient_id: Optional patient ID filter.
            
        Returns:
            QueryResponse with extraction results.
        """
        state = self.run(query, patient_id)
        
        # Create default extraction if none was produced
        if state.extraction is None:
            from src.models.schemas import DataCompleteness
            state.extraction = ClinicalExtraction(
                data_completeness=DataCompleteness.MISSING,
                confidence_score=0.0,
                clinical_explanation="No clinical information could be extracted.",
            )
        
        return QueryResponse(
            query=query,
            extraction=state.extraction,
            retrieved_chunks=state.retrieved_chunks,
            processing_time_ms=state.processing_time_ms,
        )


# Try to create LangGraph-based workflow if available
def create_langgraph_workflow(top_k: int = 5):
    """
    Create a LangGraph StateGraph workflow.
    
    This is the target architecture for Phase 2.
    Falls back to simple workflow if LangGraph is not available.
    """
    try:
        from langgraph.graph import StateGraph, END
        
        # Create agents
        retrieval_agent = RetrievalAgent(top_k=top_k)
        extraction_agent = ExtractionAgent()
        validation_agent = ValidationAgent()
        explanation_agent = ExplanationAgent()
        
        # Define the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("retrieve", retrieval_agent.run)
        workflow.add_node("extract", extraction_agent.run)
        workflow.add_node("validate", validation_agent.run)
        workflow.add_node("explain", explanation_agent.run)
        
        # Add edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "extract")
        workflow.add_edge("extract", "validate")
        workflow.add_edge("validate", "explain")
        workflow.add_edge("explain", END)
        
        # Compile
        app = workflow.compile()
        
        logger.info("Created LangGraph workflow")
        return app
        
    except ImportError:
        logger.warning("LangGraph not available, using simple workflow")
        return None
    except Exception as e:
        logger.warning(f"Failed to create LangGraph workflow: {e}")
        return None


# Global workflow instance
_workflow: Optional[ClinicalExtractionWorkflow] = None


def get_workflow() -> ClinicalExtractionWorkflow:
    """Get or create the global workflow."""
    global _workflow
    if _workflow is None:
        _workflow = ClinicalExtractionWorkflow()
    return _workflow
