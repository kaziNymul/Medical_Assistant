"""Test configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment."""
    import os
    
    # Ensure we're in test mode
    os.environ["APP_ENV"] = "development"
    os.environ["DEBUG"] = "true"
    os.environ["ENABLE_PII_MASKING"] = "true"
    os.environ["LLM_PROVIDER"] = "local"
    
    yield
    
    # Cleanup if needed


@pytest.fixture
def sample_clinical_text():
    """Provide sample clinical text for testing."""
    return """
    DISCHARGE SUMMARY
    
    Patient: John Smith
    DOB: 01/15/1960
    MRN: ABC123456
    
    Primary Diagnosis: Type 2 Diabetes Mellitus, uncontrolled
    
    History of Present Illness:
    65-year-old male with 10-year history of Type 2 Diabetes presents
    for routine follow-up. Recent HbA1c: 8.5% (previous: 9.2%).
    
    Current Medications:
    - Metformin 1000mg twice daily
    - Glipizide 10mg daily
    - Lisinopril 20mg daily
    - Atorvastatin 40mg at bedtime
    
    Social History:
    Former smoker, quit 10 years ago.
    Denies alcohol use.
    
    Complications:
    - Diabetic peripheral neuropathy
    - Mild non-proliferative retinopathy
    
    Plan:
    Continue current medications.
    Follow up in 3 months.
    
    Attending: Dr. Sarah Johnson
    St. Mary's Hospital
    Contact: 555-123-4567
    """


@pytest.fixture
def sample_extraction_result():
    """Provide sample extraction result for testing."""
    return {
        "primary_diagnosis": "Type 2 Diabetes Mellitus",
        "latest_hba1c": "8.5%",
        "hba1c_trend": "improving",
        "medications": ["Metformin", "Glipizide", "Lisinopril", "Atorvastatin"],
        "smoking_status": "former_smoker",
        "complications": ["Neuropathy", "Retinopathy"],
        "evidence": [
            {
                "field": "primary_diagnosis",
                "quote": "Primary Diagnosis: Type 2 Diabetes Mellitus",
                "confidence": 0.95,
            },
            {
                "field": "latest_hba1c",
                "quote": "Recent HbA1c: 8.5%",
                "confidence": 0.98,
            },
        ],
        "field_confidences": {
            "primary_diagnosis": 0.95,
            "latest_hba1c": 0.98,
            "medications": 0.90,
        },
    }
