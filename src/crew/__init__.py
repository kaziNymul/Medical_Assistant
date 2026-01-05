"""
CrewAI Module for Medical Documentation.

Provides the 5-agent clinical documentation workflow:
1. Medical Record Retriever Agent
2. Clinical Information Extractor Agent
3. Risk & Trend Analyst Agent
4. Clinical Gaps Finder Agent
5. Case Brief Writer Agent
"""

from src.crew.crew import (
    ClinicalDocumentationCrew,
    QuickExtractionCrew,
    get_clinical_crew,
    get_quick_crew,
)
from src.crew.agents import (
    create_retriever_agent,
    create_extractor_agent,
    create_risk_analyst_agent,
    create_gaps_finder_agent,
    create_case_brief_agent,
    create_all_agents,
)
from src.crew.tools import (
    RAGSearchTool,
    ClinicalExtractionTool,
    RiskAnalysisTool,
    InformationGapsTool,
    PIILookupTool,
    get_all_tools,
)
from src.crew.tasks import (
    create_retrieval_task,
    create_extraction_task,
    create_risk_analysis_task,
    create_gaps_finding_task,
    create_case_brief_task,
    create_all_tasks,
)

__all__ = [
    # Crews
    "ClinicalDocumentationCrew",
    "QuickExtractionCrew",
    "get_clinical_crew",
    "get_quick_crew",
    # Agents
    "create_retriever_agent",
    "create_extractor_agent",
    "create_risk_analyst_agent",
    "create_gaps_finder_agent",
    "create_case_brief_agent",
    "create_all_agents",
    # Tools
    "RAGSearchTool",
    "ClinicalExtractionTool",
    "RiskAnalysisTool",
    "InformationGapsTool",
    "PIILookupTool",
    "get_all_tools",
    # Tasks
    "create_retrieval_task",
    "create_extraction_task",
    "create_risk_analysis_task",
    "create_gaps_finding_task",
    "create_case_brief_task",
    "create_all_tasks",
]
