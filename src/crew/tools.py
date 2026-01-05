"""
CrewAI Tools for Medical Documentation.

Custom tools that agents use to perform their tasks:
- RAG Search Tool: Search vector store for relevant documents
- PII Lookup Tool: Retrieve original PII from secure storage
- Lab Analysis Tool: Analyze lab value trends
"""

from crewai.tools import BaseTool
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ============================================================
# TOOL 1: RAG Search Tool
# ============================================================
class RAGSearchInput(BaseModel):
    """Input schema for RAG search."""
    query: str = Field(..., description="The clinical query to search for")
    top_k: int = Field(default=5, description="Number of results to return")
    patient_id: Optional[str] = Field(default=None, description="Patient ID filter")


class RAGSearchTool(BaseTool):
    """
    Search the clinical knowledge base for relevant documents.
    
    Uses FAISS vector store with Bedrock Titan embeddings
    to find semantically similar medical records.
    """
    name: str = "rag_search"
    description: str = """
    Search the clinical knowledge base for relevant patient records.
    Use this tool to find medical notes, lab results, and clinical documents
    related to a patient case.
    
    Input: A clinical query describing what information you need.
    Output: Relevant document chunks with source information.
    """
    args_schema: Type[BaseModel] = RAGSearchInput
    
    def _ensure_vault_secrets(self):
        """Load Vault secrets into environment before using Bedrock."""
        import hvac
        vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN", "dev-token-medical")
        
        try:
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
        except Exception as e:
            print(f"Warning: Could not load Vault secrets: {e}")
    
    def _run(self, query: str, top_k: int = 5, patient_id: str = None) -> str:
        """Execute the RAG search."""
        try:
            # Ensure AWS credentials are set
            self._ensure_vault_secrets()
            
            from src.rag.pipeline import get_rag_pipeline
            
            pipeline = get_rag_pipeline()
            context, chunks = pipeline.get_context(
                query=query,
                top_k=top_k,
                patient_id=patient_id,
            )
            
            results = []
            for i, chunk in enumerate(chunks):
                results.append({
                    "rank": i + 1,
                    "content": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
                    "source": chunk.metadata.get("source", "unknown"),
                    "record_id": chunk.metadata.get("record_id", "unknown"),
                    "score": chunk.metadata.get("score", 0),
                })
            
            return json.dumps({
                "query": query,
                "num_results": len(results),
                "context": context[:2000] if len(context) > 2000 else context,
                "chunks": results,
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e), "query": query})


# ============================================================
# TOOL 2: Clinical Data Extraction Tool
# ============================================================
class ExtractionInput(BaseModel):
    """Input schema for clinical extraction."""
    text: str = Field(..., description="The clinical text to extract information from")


class ClinicalExtractionTool(BaseTool):
    """
    Extract structured clinical information from text.
    
    Uses pattern matching and NLP to identify clinical entities.
    """
    name: str = "extract_clinical_data"
    description: str = """
    Extract structured clinical information from medical text.
    Identifies diagnoses, medications, lab values, vitals, and other clinical data.
    
    Input: Raw clinical text (notes, reports, etc.)
    Output: Structured JSON with extracted clinical entities.
    """
    args_schema: Type[BaseModel] = ExtractionInput
    
    def _run(self, text: str) -> str:
        """Extract clinical data from text."""
        import re
        
        result = {
            "chief_complaint": None,
            "diagnoses": [],
            "medications": [],
            "allergies": [],
            "lab_values": [],
            "vital_signs": [],
            "smoking_status": None,
            "symptoms": [],
            "evidence": [],
        }
        
        text_lower = text.lower()
        
        # Extract chief complaint
        cc_patterns = [
            r'(?:chief complaint|cc|presenting complaint|reason for visit)[\s:]+([^\n\.]+)',
            r'(?:patient presents with|presents for)[\s:]+([^\n\.]+)',
        ]
        for pattern in cc_patterns:
            match = re.search(pattern, text_lower)
            if match:
                result["chief_complaint"] = match.group(1).strip().capitalize()
                result["evidence"].append({
                    "field": "chief_complaint",
                    "quote": match.group(0)[:100],
                })
                break
        
        # Extract diagnoses
        diagnosis_patterns = [
            r'(?:diagnosis|dx|assessment|impression)[\s:]+([^\n]+)',
        ]
        for pattern in diagnosis_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                # Split by common separators
                for diag in re.split(r'[,;]', match):
                    diag = diag.strip()
                    if diag and len(diag) > 3:
                        result["diagnoses"].append(diag.title())
        
        # Extract medications
        medication_keywords = [
            "metformin", "insulin", "glipizide", "glimepiride", "sitagliptin",
            "lisinopril", "amlodipine", "atorvastatin", "aspirin", "omeprazole",
            "levothyroxine", "metoprolol", "losartan", "gabapentin", "prednisone",
            "pantoprazole", "furosemide", "hydrochlorothiazide", "warfarin",
            "linagliptin", "empagliflozin", "semaglutide", "ozempic", "jardiance",
        ]
        for med in medication_keywords:
            if med in text_lower:
                result["medications"].append(med.title())
        
        # Extract allergies
        allergy_patterns = [
            r'(?:allergies?|allergic to|nkda)[\s:]+([^\n]+)',
            r'(?:adverse reactions?)[\s:]+([^\n]+)',
        ]
        for pattern in allergy_patterns:
            match = re.search(pattern, text_lower)
            if match:
                allergies_text = match.group(1)
                if "no known" not in allergies_text and "nkda" not in allergies_text:
                    result["allergies"].append(allergies_text.strip().title())
        
        # Extract lab values
        lab_patterns = {
            "HbA1c": r'(?:hba1c|a1c|hemoglobin a1c)[\s:]*(\d+\.?\d*)[\s]*(%)?',
            "Glucose": r'(?:glucose|blood sugar|bs)[\s:]*(\d+)[\s]*(mg/dl)?',
            "Creatinine": r'(?:creatinine|cr)[\s:]*(\d+\.?\d*)[\s]*(mg/dl)?',
            "eGFR": r'(?:egfr|gfr)[\s:]*(\d+)',
            "Blood Pressure": r'(?:bp|blood pressure)[\s:]*(\d+/\d+)',
        }
        for lab_name, pattern in lab_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                result["lab_values"].append({
                    "name": lab_name,
                    "value": match.group(1),
                    "unit": match.group(2) if len(match.groups()) > 1 else "",
                })
        
        # Extract smoking status
        smoking_patterns = {
            "current_smoker": [r'current\s+smoker', r'smokes', r'smoking:\s*yes', r'active\s+smoker'],
            "former_smoker": [r'former\s+smoker', r'quit\s+smoking', r'ex-smoker', r'stopped\s+smoking'],
            "never_smoked": [r'never\s+smoked', r'non-smoker', r'no\s+smoking', r'smoking:\s*no'],
        }
        for status, patterns in smoking_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    result["smoking_status"] = status.replace("_", " ").title()
                    break
            if result["smoking_status"]:
                break
        
        # Extract symptoms
        symptom_keywords = [
            "pain", "fatigue", "weakness", "nausea", "vomiting", "dizziness",
            "headache", "fever", "cough", "shortness of breath", "dyspnea",
            "chest pain", "palpitations", "swelling", "edema", "numbness",
            "tingling", "blurred vision", "polyuria", "polydipsia", "weight loss",
        ]
        for symptom in symptom_keywords:
            if symptom in text_lower:
                result["symptoms"].append(symptom.title())
        
        return json.dumps(result, indent=2)


# ============================================================
# TOOL 3: Risk Analysis Tool
# ============================================================
class RiskAnalysisInput(BaseModel):
    """Input schema for risk analysis."""
    clinical_data: str = Field(..., description="JSON string of extracted clinical data")


class RiskAnalysisTool(BaseTool):
    """
    Analyze clinical data for risk signals.
    
    Identifies trends and patterns that may indicate clinical concerns.
    """
    name: str = "analyze_clinical_risks"
    description: str = """
    Analyze extracted clinical data to identify risk signals and trends.
    Looks for patterns like deteriorating lab values, medication issues,
    and lifestyle risk factors.
    
    Input: JSON string of extracted clinical data
    Output: Risk signals with evidence and confidence levels
    """
    args_schema: Type[BaseModel] = RiskAnalysisInput
    
    def _run(self, clinical_data: str) -> str:
        """Analyze for risk signals."""
        try:
            data = json.loads(clinical_data)
        except:
            data = {}
        
        risk_signals = []
        
        # Check HbA1c levels
        lab_values = data.get("lab_values", [])
        for lab in lab_values:
            if lab.get("name") == "HbA1c":
                try:
                    value = float(lab["value"])
                    if value >= 9.0:
                        risk_signals.append({
                            "description": f"Elevated HbA1c at {value}% indicates poor glycemic control",
                            "evidence": f"HbA1c: {value}%",
                            "trend_direction": "concerning",
                            "confidence": 0.9,
                            "category": "lab_abnormality",
                        })
                    elif value >= 7.5:
                        risk_signals.append({
                            "description": f"HbA1c at {value}% is above target for most diabetic patients",
                            "evidence": f"HbA1c: {value}%",
                            "trend_direction": "needs_attention",
                            "confidence": 0.8,
                            "category": "lab_abnormality",
                        })
                except:
                    pass
            
            # Check eGFR for kidney function
            if lab.get("name") == "eGFR":
                try:
                    value = float(lab["value"])
                    if value < 60:
                        risk_signals.append({
                            "description": f"Reduced kidney function with eGFR {value}",
                            "evidence": f"eGFR: {value}",
                            "trend_direction": "concerning",
                            "confidence": 0.85,
                            "category": "kidney_function",
                        })
                except:
                    pass
        
        # Check smoking status
        smoking = data.get("smoking_status", "")
        if smoking and "current" in smoking.lower():
            risk_signals.append({
                "description": "Active smoker - cardiovascular and respiratory risk factor",
                "evidence": f"Smoking status: {smoking}",
                "trend_direction": "modifiable_risk",
                "confidence": 0.95,
                "category": "lifestyle",
            })
        
        # Check for concerning symptoms
        symptoms = data.get("symptoms", [])
        concerning_symptoms = ["chest pain", "shortness of breath", "dyspnea"]
        for symptom in symptoms:
            if symptom.lower() in concerning_symptoms:
                risk_signals.append({
                    "description": f"Patient reports {symptom} - requires clinical evaluation",
                    "evidence": f"Symptom: {symptom}",
                    "trend_direction": "needs_evaluation",
                    "confidence": 0.7,
                    "category": "symptoms",
                })
        
        return json.dumps({
            "risk_signals": risk_signals,
            "total_risks_identified": len(risk_signals),
        }, indent=2)


# ============================================================
# TOOL 4: Information Gaps Tool
# ============================================================
class GapsAnalysisInput(BaseModel):
    """Input schema for gaps analysis."""
    clinical_data: str = Field(..., description="JSON string of extracted clinical data")


class InformationGapsTool(BaseTool):
    """
    Identify missing or incomplete clinical information.
    
    Helps clinicians know what to ask during consultations.
    """
    name: str = "find_information_gaps"
    description: str = """
    Analyze extracted clinical data to identify missing, incomplete,
    or unclear information that may need clarification.
    
    Input: JSON string of extracted clinical data
    Output: List of information gaps with clinical relevance
    """
    args_schema: Type[BaseModel] = GapsAnalysisInput
    
    def _run(self, clinical_data: str) -> str:
        """Find information gaps."""
        try:
            data = json.loads(clinical_data)
        except:
            data = {}
        
        gaps = []
        
        # Check for missing chief complaint
        if not data.get("chief_complaint"):
            gaps.append({
                "gap_description": "Chief complaint / reason for visit not documented",
                "why_it_matters": "Essential for understanding the primary focus of the encounter",
                "related_to": "symptoms",
            })
        
        # Check for missing allergies
        if not data.get("allergies"):
            gaps.append({
                "gap_description": "Allergy status not documented",
                "why_it_matters": "Critical for safe medication prescribing",
                "related_to": "medications",
            })
        
        # Check for missing smoking status
        if not data.get("smoking_status"):
            gaps.append({
                "gap_description": "Smoking status not documented",
                "why_it_matters": "Important cardiovascular and respiratory risk factor",
                "related_to": "lifestyle",
            })
        
        # Check for missing medications
        if not data.get("medications"):
            gaps.append({
                "gap_description": "Current medications not documented",
                "why_it_matters": "Essential for medication reconciliation and avoiding interactions",
                "related_to": "medications",
            })
        
        # Check for missing lab values if diagnoses suggest they're needed
        diagnoses = [d.lower() for d in data.get("diagnoses", [])]
        lab_values = data.get("lab_values", [])
        lab_names = [l.get("name", "").lower() for l in lab_values]
        
        # Diabetes without HbA1c
        if any("diabet" in d for d in diagnoses) and "hba1c" not in lab_names:
            gaps.append({
                "gap_description": "HbA1c not documented for diabetic patient",
                "why_it_matters": "Key metric for glycemic control assessment",
                "related_to": "labs",
            })
        
        # Check for missing symptoms duration
        symptoms = data.get("symptoms", [])
        if symptoms and not data.get("symptom_duration"):
            gaps.append({
                "gap_description": "Duration of symptoms not specified",
                "why_it_matters": "Helps differentiate acute vs chronic conditions",
                "related_to": "symptoms",
            })
        
        return json.dumps({
            "information_gaps": gaps,
            "total_gaps_identified": len(gaps),
        }, indent=2)


# ============================================================
# TOOL 5: PII Lookup Tool (Secure)
# ============================================================
class PIILookupInput(BaseModel):
    """Input schema for PII lookup."""
    record_id: str = Field(..., description="The record ID to look up PII for")


class PIILookupTool(BaseTool):
    """
    Retrieve original PII for a record (clinician access only).
    
    This tool is restricted and logs all access for HIPAA compliance.
    """
    name: str = "lookup_patient_pii"
    description: str = """
    Retrieve the original patient identifying information for a record.
    This is a RESTRICTED tool for authorized clinical use only.
    All access is logged for HIPAA compliance.
    
    Input: Record ID
    Output: Original PII (patient name, doctor name, hospital)
    """
    args_schema: Type[BaseModel] = PIILookupInput
    
    def _run(self, record_id: str) -> str:
        """Look up PII for a record."""
        try:
            from src.data.pii_db import get_pii_db
            
            db = get_pii_db()
            pii = db.get_pii(record_id)
            
            if pii:
                return json.dumps({
                    "record_id": record_id,
                    "patient_name": pii.get("patient_name", "[PATIENT_NAME]"),
                    "doctor_name": pii.get("doctor_name", "[DOCTOR]"),
                    "hospital_name": pii.get("hospital_name", "[HOSPITAL]"),
                    "access_logged": True,
                }, indent=2)
            else:
                return json.dumps({
                    "record_id": record_id,
                    "error": "Record not found",
                })
                
        except Exception as e:
            return json.dumps({
                "record_id": record_id,
                "error": str(e),
            })


# ============================================================
# UTILITY: Get all tools
# ============================================================
def get_all_tools() -> dict:
    """
    Get all CrewAI tools organized by agent.
    
    Returns:
        Dictionary mapping agent names to their tools
    """
    return {
        "retriever": [RAGSearchTool()],
        "extractor": [ClinicalExtractionTool()],
        "risk_analyst": [RiskAnalysisTool()],
        "gaps_finder": [InformationGapsTool()],
        "case_brief": [],  # Uses results from other agents
    }


def get_tool_list() -> list:
    """Get a flat list of all tools."""
    return [
        RAGSearchTool(),
        ClinicalExtractionTool(),
        RiskAnalysisTool(),
        InformationGapsTool(),
        PIILookupTool(),
    ]
