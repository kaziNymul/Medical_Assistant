"""
CrewAI Clinical Documentation Crew.

Orchestrates the 5-agent workflow for clinical case briefings:
1. Medical Record Retriever → Finds relevant records
2. Clinical Information Extractor → Extracts structured data
3. Risk & Trend Analyst → Identifies risk signals
4. Clinical Gaps Finder → Finds missing information
5. Case Brief Writer → Creates final briefing

All agents work with de-identified data following
healthcare safety and privacy guidelines.
"""

from crewai import Crew, Process
from typing import Any, Optional
from datetime import datetime
import json
import logging

from src.crew.agents import create_all_agents
from src.crew.tools import get_all_tools
from src.crew.tasks import create_all_tasks

logger = logging.getLogger(__name__)


class ClinicalDocumentationCrew:
    """
    CrewAI-based clinical documentation workflow.
    
    Implements the 5-agent pipeline from prompt.md for
    preparing clinical case briefings.
    """
    
    def __init__(self, verbose: bool = True):
        """
        Initialize the clinical documentation crew.
        
        Args:
            verbose: Whether to show detailed agent output
        """
        self.verbose = verbose
        self._crew = None
        self._agents = None
        self._tools = None
    
    def _setup(self):
        """Set up agents and tools if not already done."""
        if self._agents is None:
            logger.info("Setting up CrewAI agents and tools...")
            
            # Get tools for each agent
            self._tools = get_all_tools()
            
            # Create agents with their tools
            self._agents = create_all_agents(self._tools)
            
            logger.info("CrewAI setup complete - 5 agents ready")
    
    def run(
        self,
        query: str,
        patient_id: Optional[str] = None,
    ) -> dict:
        """
        Run the clinical documentation workflow.
        
        Args:
            query: The clinical query or case context
            patient_id: Optional patient ID filter
            
        Returns:
            Dictionary with the case briefing and metadata
        """
        self._setup()
        
        start_time = datetime.utcnow()
        logger.info(f"Starting clinical documentation crew for query: {query[:100]}...")
        
        try:
            # Build context string
            context = query
            if patient_id:
                context = f"Patient ID: {patient_id}\n\n{query}"
            
            # Create tasks
            tasks = create_all_tasks(self._agents, context)
            
            # Create the crew
            # Note: memory=False to avoid OpenAI dependency for embeddings
            crew = Crew(
                agents=list(self._agents.values()),
                tasks=tasks,
                process=Process.sequential,  # Tasks run in order
                verbose=self.verbose,
                memory=False,  # Disabled to avoid OpenAI embeddings dependency
            )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            logger.info(f"Crew completed in {processing_time:.1f}s")
            
            return {
                "success": True,
                "query": query,
                "patient_id": patient_id,
                "case_brief": str(result),
                "processing_time_seconds": processing_time,
                "timestamp": end_time.isoformat(),
                "agents_used": list(self._agents.keys()),
            }
            
        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            return {
                "success": False,
                "query": query,
                "patient_id": patient_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def arun(
        self,
        query: str,
        patient_id: Optional[str] = None,
    ) -> dict:
        """
        Async version of run for FastAPI integration.
        
        Currently wraps synchronous execution.
        CrewAI native async support can be added when available.
        """
        import asyncio
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run(query, patient_id)
        )


# ============================================================
# Simplified Crew for Quick Queries
# ============================================================
class QuickExtractionCrew:
    """
    Simplified 2-agent crew for quick extractions.
    
    Uses only:
    1. Retriever Agent
    2. Extractor Agent
    
    For faster responses when full case briefings aren't needed.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._tools = None
        self._retriever = None
        self._extractor = None
    
    def _setup(self):
        """Set up the quick extraction agents."""
        if self._retriever is None:
            from src.crew.agents import create_retriever_agent, create_extractor_agent
            from src.crew.tools import RAGSearchTool, ClinicalExtractionTool
            
            self._retriever = create_retriever_agent([RAGSearchTool()])
            self._extractor = create_extractor_agent([ClinicalExtractionTool()])
    
    def run(self, query: str, patient_id: str = None) -> dict:
        """Run quick extraction."""
        self._setup()
        
        from src.crew.tasks import create_retrieval_task, create_extraction_task
        
        start_time = datetime.utcnow()
        
        try:
            # Create tasks
            retrieval_task = create_retrieval_task(self._retriever, query)
            extraction_task = create_extraction_task(
                self._extractor, 
                context=[retrieval_task]
            )
            
            # Create minimal crew
            crew = Crew(
                agents=[self._retriever, self._extractor],
                tasks=[retrieval_task, extraction_task],
                process=Process.sequential,
                verbose=self.verbose,
            )
            
            result = crew.kickoff()
            
            end_time = datetime.utcnow()
            
            return {
                "success": True,
                "extraction": str(result),
                "processing_time_seconds": (end_time - start_time).total_seconds(),
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


# ============================================================
# Global Crew Instance
# ============================================================
_crew_instance: Optional[ClinicalDocumentationCrew] = None
_quick_crew_instance: Optional[QuickExtractionCrew] = None


def get_clinical_crew() -> ClinicalDocumentationCrew:
    """Get or create the clinical documentation crew."""
    global _crew_instance
    if _crew_instance is None:
        _crew_instance = ClinicalDocumentationCrew(verbose=True)
    return _crew_instance


def get_quick_crew() -> QuickExtractionCrew:
    """Get or create the quick extraction crew."""
    global _quick_crew_instance
    if _quick_crew_instance is None:
        _quick_crew_instance = QuickExtractionCrew(verbose=False)
    return _quick_crew_instance
