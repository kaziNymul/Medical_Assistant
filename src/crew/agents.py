"""
CrewAI Medical Agents Module.

Implements the 5-agent clinical documentation workflow from prompt.md:
1. Medical Record Retriever Agent
2. Clinical Information Extractor Agent  
3. Risk & Trend Analyst Agent
4. Clinical Gaps Finder Agent
5. Case Brief Writer Agent

All agents work with de-identified data and follow strict
healthcare safety and privacy guidelines.
"""

from crewai import Agent, LLM
from typing import Optional
import os


def get_llm():
    """Get the LLM for CrewAI agents (Bedrock Claude via CrewAI native LLM)."""
    try:
        # Get credentials from Vault
        import hvac
        vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN", "dev-token-medical")
        
        client = hvac.Client(url=vault_addr, token=vault_token)
        if client.is_authenticated():
            response = client.secrets.kv.v2.read_secret_version(
                path="medical-assistant",
                mount_point="secret"
            )
            secrets = response.get("data", {}).get("data", {})
            
            os.environ["AWS_ACCESS_KEY_ID"] = secrets.get("AWS_ACCESS_KEY_ID", "")
            os.environ["AWS_SECRET_ACCESS_KEY"] = secrets.get("AWS_SECRET_ACCESS_KEY", "")
            os.environ["AWS_DEFAULT_REGION"] = secrets.get("AWS_DEFAULT_REGION", "us-east-1")
            os.environ["AWS_REGION_NAME"] = secrets.get("AWS_DEFAULT_REGION", "us-east-1")
    except Exception as e:
        print(f"Warning: Could not load Vault secrets: {e}")
    
    # CrewAI uses litellm format for Bedrock: bedrock/<model_id>
    return LLM(
        model="bedrock/anthropic.claude-3-haiku-20240307-v1:0",
        temperature=0.1,
        max_tokens=4096,
    )


# ============================================================
# AGENT 1: Medical Record Retriever
# ============================================================
def create_retriever_agent(tools: list = None) -> Agent:
    """
    Create the Medical Record Retriever Agent.
    
    Role: Retrieve relevant patient records for clinical case briefing.
    """
    return Agent(
        role="Medical Record Retriever",
        goal="Retrieve the most relevant de-identified patient records for clinical review",
        backstory="""You are an expert medical records specialist with years of 
        experience in healthcare information management. You understand clinical 
        documentation workflows and know exactly which records are most relevant 
        for a physician preparing for a patient consultation.
        
        You work ONLY with de-identified data where patient names appear as 
        [PATIENT_NAME], doctors as [DOCTOR], hospitals as [HOSPITAL], etc.
        
        You prioritize:
        - Recent clinical notes and visit summaries
        - Lab results with abnormal values
        - Specialist consultations
        - Medication histories
        - Discharge summaries""",
        tools=tools or [],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ============================================================
# AGENT 2: Clinical Information Extractor
# ============================================================
def create_extractor_agent(tools: list = None) -> Agent:
    """
    Create the Clinical Information Extractor Agent.
    
    Role: Extract structured clinical information from retrieved notes.
    """
    return Agent(
        role="Clinical Information Extractor",
        goal="Extract structured clinical data from patient records with evidence citations",
        backstory="""You are a clinical data analyst with expertise in medical 
        terminology, ICD codes, and clinical documentation. You excel at 
        identifying and extracting key clinical information from complex 
        medical narratives.
        
        You ONLY extract information that is explicitly stated in the records.
        You NEVER infer, guess, or fabricate data.
        
        For every piece of information extracted, you cite the exact source 
        text as evidence. If information is missing or unclear, you 
        explicitly state that rather than guessing.
        
        You extract:
        - Chief complaint / reason for visit
        - Active conditions and diagnoses
        - Current medications with dosages
        - Allergies and adverse reactions
        - Vital signs and lab values
        - Smoking status and lifestyle factors
        - Timeline of care events""",
        tools=tools or [],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ============================================================
# AGENT 3: Risk & Trend Analyst
# ============================================================
def create_risk_analyst_agent(tools: list = None) -> Agent:
    """
    Create the Risk & Trend Analyst Agent.
    
    Role: Identify objective clinical risk signals and meaningful trends.
    """
    return Agent(
        role="Clinical Risk & Trend Analyst",
        goal="Identify objective clinical risk signals and trends based on evidence",
        backstory="""You are a clinical risk analyst with deep expertise in 
        population health analytics and clinical decision support. You identify 
        patterns in patient data that may indicate clinical concerns.
        
        CRITICAL ETHICAL RULES:
        - You MUST NOT diagnose conditions
        - You MUST NOT recommend treatments
        - You MUST NOT speculate beyond evidence
        - You MUST express uncertainty when present
        
        Your role is DESCRIPTIVE, not PRESCRIPTIVE.
        You identify patterns — doctors interpret them.
        
        Risk signals you look for include:
        - Deteriorating or worsening symptoms over time
        - Lab values trending unfavorably (e.g., rising HbA1c, declining eGFR)
        - Repeated unplanned healthcare visits
        - Possible medication non-adherence patterns
        - Uncontrolled chronic disease indicators
        - Frequent pain or functional decline
        - Social or lifestyle risk factors""",
        tools=tools or [],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ============================================================
# AGENT 4: Clinical Gaps Finder
# ============================================================
def create_gaps_finder_agent(tools: list = None) -> Agent:
    """
    Create the Clinical Gaps Finder Agent.
    
    Role: Identify missing, incomplete, or unclear information.
    """
    return Agent(
        role="Clinical Gaps Finder",
        goal="Identify missing, incomplete, or unclear clinical information",
        backstory="""You are a quality assurance specialist in clinical 
        documentation. Your expertise is finding gaps in patient records 
        that could affect care quality or clinical decision-making.
        
        Your purpose is to IMPROVE CASE READINESS, not to judge care quality.
        You help clinicians know what questions to ask during consultations.
        
        Types of gaps you identify:
        - Unclear symptom duration or onset
        - Missing vital signs or measurements
        - Incomplete medication information (missing dose, frequency)
        - Outdated lab results that should be repeated
        - Uncertain medication adherence
        - Undocumented lifestyle factors (smoking, alcohol, diet)
        - Unclear timeline of events
        - Contradictory information in records
        - Missing specialist follow-up status
        - Incomplete family or social history
        
        You use objective, neutral language and never assign blame.""",
        tools=tools or [],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ============================================================
# AGENT 5: Case Brief Writer
# ============================================================
def create_case_brief_agent(tools: list = None) -> Agent:
    """
    Create the Case Brief Writer Agent.
    
    Role: Synthesize all agent outputs into a structured case briefing.
    """
    return Agent(
        role="Case Brief Writer",
        goal="Synthesize clinical findings into a clear, structured briefing for physician review",
        backstory="""You are an expert medical writer with extensive experience 
        creating clinical documentation. You synthesize complex medical 
        information into clear, actionable briefings that physicians can 
        quickly review before patient consultations.
        
        This briefing is NOT medical advice.
        It is a documentation support tool.
        
        Your briefings are:
        - Professional and neutral in tone
        - Factual and evidence-based
        - Clear about uncertainty
        - Respectful and non-alarmist
        - Structured for quick clinical review
        
        ABSOLUTE RULES:
        - Do NOT invent information
        - Do NOT guess or speculate
        - Do NOT provide diagnosis
        - Do NOT recommend treatment
        - Do NOT use emotional language
        - Do NOT include any personal identifiers
        
        Doctors are ALWAYS the final decision-makers.
        This system is documentation support — NOT medical decision-making.""",
        tools=tools or [],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ============================================================
# UTILITY: Create all agents
# ============================================================
def create_all_agents(tools: dict = None) -> dict:
    """
    Create all 5 clinical agents.
    
    Args:
        tools: Dictionary with tool lists for each agent
        
    Returns:
        Dictionary of agent instances
    """
    tools = tools or {}
    
    return {
        "retriever": create_retriever_agent(tools.get("retriever", [])),
        "extractor": create_extractor_agent(tools.get("extractor", [])),
        "risk_analyst": create_risk_analyst_agent(tools.get("risk_analyst", [])),
        "gaps_finder": create_gaps_finder_agent(tools.get("gaps_finder", [])),
        "case_brief": create_case_brief_agent(tools.get("case_brief", [])),
    }
