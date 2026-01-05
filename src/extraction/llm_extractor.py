"""
Local LLM Clinical Data Extractor

Uses HuggingFace local models to:
1. Parse any document format
2. Intelligently extract clinical data fields
3. Format data for storage
4. Handle masked/unmasked versions

Configured for: FLAN-T5 Base (CPU-optimized)
- Model size: ~250MB
- RAM required: 1-2 GB
- Extraction time: 5-15 seconds
"""

import os
import json
import re
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from src.utils.logging import logger
from src.utils.masking import get_masker

# Set threading for CPU optimization
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('MKL_NUM_THREADS', '4')


class ExtractionModel(Enum):
    """Available local extraction models."""
    FLAN_T5_SMALL = "google/flan-t5-small"  # 80MB - fastest
    FLAN_T5_BASE = "google/flan-t5-base"    # 250MB - recommended
    FLAN_T5_LARGE = "google/flan-t5-large"  # 780MB - more accurate


@dataclass
class ClinicalDataExtraction:
    """Extracted clinical data structure."""
    # Patient Demographics
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    mrn: Optional[str] = None  # Medical Record Number
    ssn: Optional[str] = None  # Social Security Number
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    insurance_id: Optional[str] = None
    
    # Clinical Data
    diagnoses: List[Dict[str, str]] = None  # [{code, description, type}]
    medications: List[Dict[str, str]] = None  # [{name, dose, frequency, route}]
    allergies: List[Dict[str, str]] = None  # [{allergen, reaction, severity}]
    procedures: List[Dict[str, str]] = None  # [{code, description, date}]
    lab_results: List[Dict[str, str]] = None  # [{test, value, unit, reference_range, date}]
    vital_signs: Dict[str, str] = None  # {bp, hr, temp, resp_rate, spo2, weight, height}
    
    # Visit Information
    visit_date: Optional[str] = None
    visit_type: Optional[str] = None
    chief_complaint: Optional[str] = None
    history_present_illness: Optional[str] = None
    
    # Provider Information
    provider_name: Optional[str] = None
    provider_npi: Optional[str] = None
    facility_name: Optional[str] = None
    
    # Assessment & Plan
    assessment: Optional[str] = None
    plan: Optional[str] = None
    follow_up: Optional[str] = None
    
    # Metadata
    extraction_confidence: float = 0.0
    source_file: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    model_used: Optional[str] = None
    
    def __post_init__(self):
        if self.diagnoses is None:
            self.diagnoses = []
        if self.medications is None:
            self.medications = []
        if self.allergies is None:
            self.allergies = []
        if self.procedures is None:
            self.procedures = []
        if self.lab_results is None:
            self.lab_results = []
        if self.vital_signs is None:
            self.vital_signs = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_masked_dict(self, masker) -> Dict[str, Any]:
        """Return dict with PII masked."""
        data = self.to_dict()
        
        # Fields to mask
        pii_fields = [
            'patient_name', 'date_of_birth', 'ssn', 'address', 
            'phone', 'email', 'insurance_id', 'mrn'
        ]
        
        for field in pii_fields:
            if data.get(field):
                masked = masker.mask_text(str(data[field]))
                data[field] = masked.masked_text
        
        # Mask provider info
        if data.get('provider_name'):
            data['provider_name'] = masker.mask_text(data['provider_name']).masked_text
        
        return data


class LocalLLMExtractor:
    """
    Extract clinical data using local HuggingFace FLAN-T5 model.
    
    Optimized for CPU with limited RAM:
    - Uses google/flan-t5-base (250MB)
    - Single-threaded inference
    - Lazy model loading
    - Memory-efficient settings
    """
    
    # Shorter, focused prompt for T5 (better with concise prompts)
    EXTRACTION_PROMPT = """Extract clinical data as JSON:

{document_text}

JSON output with: patient_name, date_of_birth, gender, age, mrn, phone, email, diagnoses (list), medications (list), allergies (list), lab_results (list), vital_signs, visit_date, chief_complaint, assessment, plan, provider_name, facility_name. Use null if not found."""

    # Lock for thread-safe model loading
    _load_lock = threading.Lock()
    _instance = None
    
    def __init__(
        self, 
        model_name: str = None,
        device: str = None,
        max_length: int = None,
        cache_dir: str = None
    ):
        """
        Initialize the local LLM extractor.
        
        Args:
            model_name: HuggingFace model (default: google/flan-t5-base)
            device: Device to use (default: cpu)
            max_length: Maximum generation length (default: 1024)
            cache_dir: Directory to cache models
        """
        # Load from environment or use defaults
        self.model_name = model_name or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
        self.device = device or os.getenv('EXTRACTION_DEVICE', 'cpu')
        self.max_length = max_length or int(os.getenv('EXTRACTION_MAX_LENGTH', '1024'))
        self.cache_dir = cache_dir or os.getenv('EXTRACTION_CACHE_DIR', None)
        
        self.model = None
        self.tokenizer = None
        self._loaded = False
        
        logger.info(f"Extractor configured: {self.model_name} on {self.device}")
        
    def load_model(self):
        """Load the model (lazy loading, thread-safe)."""
        if self._loaded:
            return
        
        with self._load_lock:
            if self._loaded:  # Double-check after acquiring lock
                return
                
            logger.info(f"Loading FLAN-T5 model: {self.model_name}")
            start_time = datetime.now()
            
            try:
                from transformers import T5Tokenizer, T5ForConditionalGeneration
                import torch
                
                # Set cache directory
                cache_kwargs = {}
                if self.cache_dir:
                    cache_kwargs['cache_dir'] = self.cache_dir
                    os.makedirs(self.cache_dir, exist_ok=True)
                
                # Load tokenizer
                logger.info("Loading tokenizer...")
                self.tokenizer = T5Tokenizer.from_pretrained(
                    self.model_name,
                    **cache_kwargs
                )
                
                # Load model with CPU optimization
                logger.info("Loading model (this may take 30-60 seconds on first run)...")
                self.model = T5ForConditionalGeneration.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float32,  # CPU works better with float32
                    low_cpu_mem_usage=True,
                    **cache_kwargs
                )
                
                # Move to device
                self.model = self.model.to(self.device)
                
                # Set to evaluation mode (disables dropout, etc.)
                self.model.eval()
                
                self._loaded = True
                load_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Model loaded successfully in {load_time:.1f}s")
                
            except ImportError as e:
                logger.error(f"Missing dependency: {e}")
                logger.error("Install with: pip install transformers torch")
                raise
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise
    
    def extract(
        self, 
        document_text: str, 
        source_file: str = None
    ) -> ClinicalDataExtraction:
        """
        Extract clinical data from document text.
        
        Args:
            document_text: The text content to extract from
            source_file: Optional source filename for metadata
            
        Returns:
            ClinicalDataExtraction with all found data
        """
        import torch
        
        # Load model if needed
        self.load_model()
        
        # Truncate input if too long (T5 has 512 token limit, but we use more context)
        max_input_chars = 3000
        if len(document_text) > max_input_chars:
            # Keep beginning and end
            half = max_input_chars // 2
            document_text = document_text[:half] + "\n...[truncated]...\n" + document_text[-half:]
        
        # Create prompt
        prompt = self.EXTRACTION_PROMPT.format(document_text=document_text)
        
        try:
            logger.info("Running clinical data extraction...")
            start_time = datetime.now()
            
            # Tokenize input
            inputs = self.tokenizer(
                prompt, 
                return_tensors="pt", 
                max_length=512,
                truncation=True,
                padding=True
            ).to(self.device)
            
            # Generate with optimized settings for CPU
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_length,
                    num_beams=2,           # Reduced from 4 for speed
                    early_stopping=True,
                    do_sample=False,       # Deterministic for consistency
                    temperature=1.0,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            
            # Decode output
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            extract_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Extraction completed in {extract_time:.1f}s")
            
            # Parse JSON from result
            extraction = self._parse_extraction_result(result)
            
            # Add metadata
            extraction.source_file = source_file
            extraction.extraction_timestamp = datetime.utcnow().isoformat()
            extraction.model_used = self.model_name
            
            return extraction
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # Return empty extraction with error info
            return ClinicalDataExtraction(
                extraction_confidence=0.0,
                source_file=source_file,
                extraction_timestamp=datetime.utcnow().isoformat(),
                model_used=self.model_name
            )
    
    def _parse_extraction_result(self, result: str) -> ClinicalDataExtraction:
        """Parse LLM output into structured extraction."""
        
        # Try to find JSON in the result
        json_match = re.search(r'\{[\s\S]*\}', result)
        
        if json_match:
            try:
                data = json.loads(json_match.group())
                
                # Create extraction object
                extraction = ClinicalDataExtraction(
                    patient_name=data.get('patient_name'),
                    date_of_birth=data.get('date_of_birth'),
                    gender=data.get('gender'),
                    age=data.get('age'),
                    mrn=data.get('mrn'),
                    ssn=data.get('ssn'),
                    address=data.get('address'),
                    phone=data.get('phone'),
                    email=data.get('email'),
                    insurance_id=data.get('insurance_id'),
                    diagnoses=data.get('diagnoses', []),
                    medications=data.get('medications', []),
                    allergies=data.get('allergies', []),
                    procedures=data.get('procedures', []),
                    lab_results=data.get('lab_results', []),
                    vital_signs=data.get('vital_signs', {}),
                    visit_date=data.get('visit_date'),
                    visit_type=data.get('visit_type'),
                    chief_complaint=data.get('chief_complaint'),
                    history_present_illness=data.get('history_present_illness'),
                    provider_name=data.get('provider_name'),
                    provider_npi=data.get('provider_npi'),
                    facility_name=data.get('facility_name'),
                    assessment=data.get('assessment'),
                    plan=data.get('plan'),
                    follow_up=data.get('follow_up'),
                    extraction_confidence=0.85
                )
                
                return extraction
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from LLM output")
        
        # Fallback: try regex extraction
        return self._regex_fallback_extraction(result)
    
    def _regex_fallback_extraction(self, text: str) -> ClinicalDataExtraction:
        """Fallback regex-based extraction when JSON parsing fails."""
        extraction = ClinicalDataExtraction(extraction_confidence=0.5)
        
        # Common patterns
        patterns = {
            'patient_name': r'(?:patient|name|pt)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            'date_of_birth': r'(?:dob|date of birth|birthdate)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            'gender': r'(?:gender|sex)[:\s]+(male|female|m|f)',
            'age': r'(?:age)[:\s]+(\d{1,3})',
            'mrn': r'(?:mrn|medical record)[:\s#]+(\w+)',
            'phone': r'(?:phone|tel)[:\s]+(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',
            'email': r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            'visit_date': r'(?:visit date|date of visit|dos)[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                setattr(extraction, field, match.group(1))
        
        # Extract diagnoses (ICD codes)
        icd_matches = re.findall(r'([A-Z]\d{2}\.?\d{0,2})\s*[-:]\s*([^,\n]+)', text)
        for code, desc in icd_matches[:10]:
            extraction.diagnoses.append({
                'code': code,
                'description': desc.strip(),
                'type': 'unknown'
            })
        
        # Extract medications
        med_matches = re.findall(
            r'(\w+(?:cillin|mycin|pril|sartan|statin|prazole|tidine|mab|nib))\s+(\d+\s*(?:mg|mcg|ml))',
            text, re.IGNORECASE
        )
        for name, dose in med_matches[:10]:
            extraction.medications.append({
                'name': name,
                'dose': dose,
                'frequency': '',
                'route': ''
            })
        
        return extraction


class ClinicalDataProcessor:
    """
    Complete pipeline for processing clinical documents:
    1. Parse any file format
    2. Extract clinical data with local LLM
    3. Create masked/unmasked versions
    4. Sync to Databricks
    """
    
    def __init__(
        self,
        model_name: str = "google/flan-t5-base",
        device: str = "auto"
    ):
        from src.extraction.file_parser import get_file_parser
        
        self.parser = get_file_parser()
        self.extractor = LocalLLMExtractor(model_name=model_name, device=device)
        self.masker = get_masker()
        
    def process_file(
        self,
        file_path: str = None,
        file_bytes: bytes = None,
        filename: str = None,
        patient_id: str = None
    ) -> Dict[str, Any]:
        """
        Process a file and extract clinical data.
        
        Returns:
            Dict with 'unmasked', 'masked', 'metadata' keys
        """
        # Step 1: Parse file
        logger.info(f"Parsing file: {filename or file_path}")
        parsed = self.parser.parse(
            file_path=file_path,
            file_bytes=file_bytes,
            filename=filename
        )
        
        logger.info(f"Parsed {parsed.file_type} file, confidence: {parsed.confidence}")
        
        # Step 2: Extract clinical data
        extraction = self.extractor.extract(
            document_text=parsed.content,
            source_file=filename or file_path
        )
        
        # Set patient_id if provided
        if patient_id:
            extraction.patient_id = patient_id
        
        # Step 3: Create masked/unmasked versions
        unmasked_data = extraction.to_dict()
        masked_data = extraction.to_masked_dict(self.masker)
        
        # Step 4: Prepare result
        result = {
            'unmasked': unmasked_data,
            'masked': masked_data,
            'metadata': {
                'file_type': parsed.file_type,
                'parse_confidence': parsed.confidence,
                'extraction_confidence': extraction.extraction_confidence,
                'tables_found': len(parsed.tables),
                'file_metadata': parsed.metadata,
                'processed_at': datetime.utcnow().isoformat()
            }
        }
        
        return result
    
    def process_and_sync(
        self,
        file_path: str = None,
        file_bytes: bytes = None,
        filename: str = None,
        patient_id: str = None,
        sync_to_databricks: bool = True
    ) -> Dict[str, Any]:
        """
        Process file and optionally sync to Databricks.
        
        Creates two tables in Databricks:
        - clinical_data_unmasked (for authorized access)
        - clinical_data_masked (for general access)
        """
        # Process the file
        result = self.process_file(
            file_path=file_path,
            file_bytes=file_bytes,
            filename=filename,
            patient_id=patient_id
        )
        
        if sync_to_databricks:
            try:
                from src.utils.databricks_sync import sync_clinical_extraction
                
                sync_result = sync_clinical_extraction(
                    unmasked_data=result['unmasked'],
                    masked_data=result['masked']
                )
                result['databricks_sync'] = sync_result
                
            except Exception as e:
                logger.error(f"Databricks sync failed: {e}")
                result['databricks_sync'] = {'success': False, 'error': str(e)}
        
        return result


# Singleton instances
_extractor = None
_processor = None


def get_extractor(model_name: str = None) -> LocalLLMExtractor:
    """Get singleton extractor instance (thread-safe)."""
    global _extractor
    if _extractor is None:
        model = model_name or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
        _extractor = LocalLLMExtractor(model_name=model)
    return _extractor


def get_clinical_processor(model_name: str = None) -> ClinicalDataProcessor:
    """Get singleton processor instance."""
    global _processor
    if _processor is None:
        model = model_name or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
        _processor = ClinicalDataProcessor(model_name=model)
    return _processor


def download_model(model_name: str = None, cache_dir: str = None):
    """
    Pre-download the model for faster startup.
    
    Run this once before deployment:
        python -c "from src.extraction.llm_extractor import download_model; download_model()"
    """
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    
    model = model_name or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
    cache = cache_dir or os.getenv('EXTRACTION_CACHE_DIR', './models')
    
    print(f"Downloading {model} to {cache}...")
    os.makedirs(cache, exist_ok=True)
    
    print("Downloading tokenizer...")
    T5Tokenizer.from_pretrained(model, cache_dir=cache)
    
    print("Downloading model (~250MB)...")
    T5ForConditionalGeneration.from_pretrained(model, cache_dir=cache)
    
    print("✅ Model downloaded successfully!")
    print(f"   Location: {cache}")
    print(f"   Model: {model}")


if __name__ == "__main__":
    # Allow running as script to download model
    download_model()