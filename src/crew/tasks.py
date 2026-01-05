"""
CrewAI Tasks for Clinical Documentation.

Defines the tasks that each agent performs, matching
the specifications in prompt.md.
"""

from crewai import Task
from typing import Any


# ============================================================
# TASK 1: Medical Record Retrieval
# ============================================================
def create_retrieval_task(agent, context: str = None) -> Task:
    """
    Create the medical record retrieval task.
    
    Agent 1's task: Retrieve relevant patient records.
    """
    return Task(
        description=f"""
        Search the patient knowledge base and retrieve the most relevant clinical records.
        
        Patient/Case Context: {context or 'General case review requested'}
        
        Your tasks:
        1. Search the patient knowledge base using the RAG search tool
        2. Retrieve the most relevant notes and documents
        3. Prefer recent and clinically significant records
        4. Include a balance of:
           - Visit summaries
           - Clinical notes  
           - Lab results
           - Specialist notes (if available)
        5. Avoid unnecessary or duplicate content
        
        RULES:
        - Retrieve ONLY de-identified records
        - NEVER output real-world identifiers
        - If retrieval confidence is low, state that clearly
        
        OUTPUT FORMAT:
        Provide a structured list of retrieved records, each with:
        - Text content summary
        - Source type (GP note, discharge summary, lab result, etc.)
        - Approximate date if available
        - Relevance rationale
        
        If no relevant records exist, return an empty list with explanation.
        """,
        expected_output="""
        A JSON object containing:
        {
            "records_found": number,
            "records": [
                {
                    "content": "...",
                    "source_type": "GP note | discharge summary | lab result | specialist note",
                    "date": "YYYY-MM-DD or 'unknown'",
                    "relevance_rationale": "..."
                }
            ],
            "retrieval_confidence": "high | medium | low",
            "notes": "Any important notes about the retrieval"
        }
        """,
        agent=agent,
    )


# ============================================================
# TASK 2: Clinical Information Extraction
# ============================================================
def create_extraction_task(agent, context: list = None) -> Task:
    """
    Create the clinical information extraction task.
    
    Agent 2's task: Extract structured clinical data.
    """
    return Task(
        description="""
        Extract clinically meaningful structured information from the retrieved notes.
        
        Extract ONLY information that is explicitly stated or clearly documented.
        
        Extract the following fields where possible:
        - Chief complaint / main reason for care
        - Active conditions / diagnoses
        - Relevant past medical history
        - Current medications (with doses if available)
        - Allergies / adverse reactions
        - Lifestyle factors (smoking, alcohol, exercise)
        - Key symptoms and duration
        - Important lab values (especially HbA1c, eGFR, lipids)
        - Specialist involvement
        - Timeline summary of care events
        
        RULES:
        - Quote the source text for each data point as evidence
        - If there is conflicting data, describe the conflict
        - NEVER infer beyond what is written in the text
        - If unsure about any field, set the value to null
        - Include confidence scores for each extraction
        """,
        expected_output="""
        A JSON object with extracted clinical data:
        {
            "chief_complaint": "..." or null,
            "conditions": ["list of active conditions"],
            "past_history": ["relevant past medical history"],
            "medications": [
                {"name": "...", "dose": "...", "frequency": "..."}
            ],
            "allergies": ["list of allergies"] or "NKDA",
            "lifestyle": {
                "smoking": "current | former | never | unknown",
                "alcohol": "...",
                "exercise": "..."
            },
            "symptoms": [
                {"symptom": "...", "duration": "..."}
            ],
            "lab_values": [
                {"name": "HbA1c", "value": "...", "date": "..."}
            ],
            "specialists": ["list of specialists involved"],
            "timeline_summary": "Brief chronological summary",
            "evidence": [
                {
                    "field": "medications",
                    "quote": "exact quote from source",
                    "source_type": "GP note",
                    "confidence": 0.9
                }
            ]
        }
        """,
        agent=agent,
        context=context,
    )


# ============================================================
# TASK 3: Risk & Trend Analysis
# ============================================================
def create_risk_analysis_task(agent, context: list = None) -> Task:
    """
    Create the risk and trend analysis task.
    
    Agent 3's task: Identify clinical risk signals.
    """
    return Task(
        description="""
        Identify objective clinical risk signals and meaningful trends 
        based on the extracted clinical information.
        
        Risk signals to look for include:
        - Deterioration or worsening of symptoms over time
        - Lab values trending unfavorably (rising HbA1c, declining eGFR, etc.)
        - Repeated unplanned healthcare visits
        - Possible medication non-adherence patterns
        - Uncontrolled chronic disease indicators
        - Frequent pain or functional decline
        - Social or lifestyle risk factors (smoking, poor diet, sedentary)
        - Age-related risk factors
        - Polypharmacy concerns
        
        CRITICAL ETHICAL RULES:
        - You MUST NOT diagnose any condition
        - You MUST NOT recommend any treatment
        - You MUST NOT speculate beyond the evidence
        - You MUST express uncertainty when present
        - Your role is DESCRIPTIVE, not PRESCRIPTIVE
        
        You identify patterns — doctors interpret them.
        """,
        expected_output="""
        A JSON object with identified risk signals:
        {
            "risk_signals": [
                {
                    "description": "Clear description of the risk signal",
                    "evidence_quote": "Supporting quote from the records",
                    "trend_direction": "increasing | decreasing | stable | unclear",
                    "confidence": 0.0-1.0,
                    "category": "lab_trend | symptom | lifestyle | adherence | other"
                }
            ],
            "overall_risk_level": "low | moderate | elevated | high",
            "uncertainty_notes": "Any areas of uncertainty"
        }
        """,
        agent=agent,
        context=context,
    )


# ============================================================
# TASK 4: Information Gaps Finding
# ============================================================
def create_gaps_finding_task(agent, context: list = None) -> Task:
    """
    Create the information gaps finding task.
    
    Agent 4's task: Identify missing or unclear information.
    """
    return Task(
        description="""
        Identify missing, incomplete, unclear, or outdated information 
        that a clinician may wish to clarify during the consultation.
        
        Types of gaps to look for:
        - Unclear symptom duration or onset
        - Missing vital signs or measurements
        - Missing medication details (dose, frequency, duration)
        - Outdated lab results that should be repeated
        - Uncertain medication adherence
        - Lifestyle status undocumented (smoking, alcohol, diet)
        - Unclear timeline of events
        - Contradictory documentation between records
        - Missing specialist follow-up status
        - Incomplete social or family history
        - Missing vaccination status (if relevant)
        - Unclear goals of care
        
        Your purpose is to IMPROVE CASE READINESS — not judge care quality.
        Help clinicians know what questions to ask.
        
        Use objective, neutral language. Do not assign blame or opinion.
        """,
        expected_output="""
        A JSON object with identified information gaps:
        {
            "information_gaps": [
                {
                    "gap_description": "Clear description of what's missing",
                    "why_it_matters": "Clinical relevance of this gap",
                    "related_to": "medications | labs | symptoms | history | lifestyle | other",
                    "priority": "high | medium | low"
                }
            ],
            "completeness_assessment": "complete | mostly_complete | partial | incomplete",
            "suggested_clarifications": ["List of questions to ask patient"]
        }
        """,
        agent=agent,
        context=context,
    )


# ============================================================
# TASK 5: Case Brief Writing
# ============================================================
def create_case_brief_task(agent, context: list = None) -> Task:
    """
    Create the case brief writing task.
    
    Agent 5's task: Synthesize into structured briefing.
    """
    return Task(
        description="""
        Synthesize all the outputs from the other agents into a clear, 
        structured, clinically-appropriate briefing for a doctor to review
        before a patient consultation.
        
        This briefing is NOT medical advice.
        It is a documentation support tool.
        
        BRIEFING STRUCTURE:
        
        1. OVERVIEW
           - Short neutral summary (2-3 sentences)
           - Key reason for review
        
        2. KEY HISTORY
           - Bullet list of important background information
           - Relevant past medical history
           - Current medications
        
        3. OBJECTIVE DATA
           - Labs, vitals, measurements (if available)
           - Recent test results
        
        4. RISK SIGNALS
           - Neutral statements based on evidence only
           - No diagnosis or treatment recommendations
        
        5. INFORMATION GAPS
           - Clear, objective list of missing data
           - Suggested questions for the encounter
        
        6. EVIDENCE SOURCES
           - List key document sources used
           - Include relevant quote fragments
        
        TONE REQUIREMENTS:
        - Professional
        - Neutral
        - Factual
        - Uncertainty-aware
        - Respectful
        - Non-alarmist
        
        ABSOLUTE RULES:
        - Do NOT invent information
        - Do NOT guess or speculate
        - Do NOT provide diagnosis
        - Do NOT recommend treatment
        - Do NOT use emotional language
        - Do NOT mention any personal identifiers (use placeholders)
        """,
        expected_output="""
        A structured case briefing document:
        
        ═══════════════════════════════════════════
        PATIENT CASE BRIEF — De-identified
        ═══════════════════════════════════════════
        
        📋 OVERVIEW
        [2-3 sentence summary]
        
        📚 KEY HISTORY
        • [Bullet points of important history]
        • [Current medications]
        • [Relevant past conditions]
        
        📊 OBJECTIVE DATA
        • [Lab values with dates]
        • [Vital signs]
        • [Other measurements]
        
        ⚠️ RISK SIGNALS
        • [Identified risk patterns - descriptive only]
        • [Trend observations]
        
        ❓ INFORMATION GAPS
        • [Missing information to clarify]
        • [Suggested questions for consultation]
        
        📄 EVIDENCE SOURCES
        • [Source documents referenced]
        • [Key quotes supporting findings]
        
        ═══════════════════════════════════════════
        ⚕️ DISCLAIMER: Documentation support only.
        Clinical decisions remain with the physician.
        ═══════════════════════════════════════════
        """,
        agent=agent,
        context=context,
    )


# ============================================================
# UTILITY: Create all tasks
# ============================================================
def create_all_tasks(agents: dict, query: str) -> list:
    """
    Create all 5 tasks in sequence.
    
    Args:
        agents: Dictionary of agent instances
        query: The clinical query/context
        
    Returns:
        List of tasks in execution order
    """
    # Task 1: Retrieval (no dependencies)
    retrieval_task = create_retrieval_task(
        agent=agents["retriever"],
        context=query,
    )
    
    # Task 2: Extraction (depends on retrieval)
    extraction_task = create_extraction_task(
        agent=agents["extractor"],
        context=[retrieval_task],
    )
    
    # Task 3: Risk Analysis (depends on extraction)
    risk_task = create_risk_analysis_task(
        agent=agents["risk_analyst"],
        context=[extraction_task],
    )
    
    # Task 4: Gaps Finding (depends on extraction)
    gaps_task = create_gaps_finding_task(
        agent=agents["gaps_finder"],
        context=[extraction_task],
    )
    
    # Task 5: Case Brief (depends on all previous)
    brief_task = create_case_brief_task(
        agent=agents["case_brief"],
        context=[extraction_task, risk_task, gaps_task],
    )
    
    return [retrieval_task, extraction_task, risk_task, gaps_task, brief_task]
