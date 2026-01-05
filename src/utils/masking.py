"""
PII Masking and De-identification Utilities.

This module provides healthcare-grade masking for Protected Health Information (PHI)
and Personally Identifiable Information (PII).

CRITICAL: All text must be masked before sending to LLM or storage.

Masked entities:
- Patient names → [PATIENT_NAME]
- Doctor names → [DOCTOR_NAME]
- Hospital names → [HOSPITAL]
- Email addresses → [EMAIL]
- Phone numbers → [PHONE]
- SSN → [SSN]
- Dates of birth → [DOB]
- Addresses → [ADDRESS]
- Medical record numbers → [MRN]
"""

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from config.settings import settings


@dataclass
class MaskingResult:
    """Result of a masking operation."""
    masked_text: str
    original_text: str
    pii_detected: bool
    items_masked: int
    mask_mapping: dict[str, str]  # original -> masked for reversibility if needed


class PIIMasker:
    """
    Healthcare-grade PII/PHI masking utility.
    
    Follows HIPAA Safe Harbor guidelines for de-identification.
    """
    
    # Common name patterns (simplified - in production use NER)
    NAME_PREFIXES = [
        "Mr.", "Mrs.", "Ms.", "Miss", "Dr.", "Prof.",
        "Patient:", "Patient", "Name:", "Pt:", "Pt."
    ]
    
    # Regex patterns for PII detection
    PATTERNS = {
        "email": re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        ),
        "phone": re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
        ),
        "ssn": re.compile(
            r'\b[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4}\b'
        ),
        "dob": re.compile(
            r'\b(?:DOB|Date of Birth|D\.O\.B\.?)[\s:]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b',
            re.IGNORECASE
        ),
        "mrn": re.compile(
            r'\b(?:MRN|Medical Record Number|Med Rec|Record #?)[\s:]*([A-Z0-9]{6,12})\b',
            re.IGNORECASE
        ),
        "address": re.compile(
            r'\b\d{1,5}\s+(?:[A-Za-z]+\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir)\.?\s*(?:#\s*\d+|Apt\.?\s*\d+|Suite\s*\d+)?\b',
            re.IGNORECASE
        ),
        "zip_code": re.compile(
            r'\b[0-9]{5}(?:-[0-9]{4})?\b'
        ),
    }
    
    # Hospital/facility indicators
    FACILITY_INDICATORS = [
        "Hospital", "Medical Center", "Clinic", "Healthcare",
        "Health System", "Medical Group", "Health Center",
        "Memorial", "General Hospital", "University Hospital"
    ]
    
    def __init__(self, enabled: bool = True):
        """
        Initialize the PII masker.
        
        Args:
            enabled: Whether masking is enabled. Should always be True in production.
        """
        self.enabled = enabled
        self._mask_counter = 0
        
    def mask_text(self, text: str) -> MaskingResult:
        """
        Mask all PII/PHI in the given text.
        
        Args:
            text: The text to mask.
            
        Returns:
            MaskingResult with masked text and metadata.
        """
        if not self.enabled:
            return MaskingResult(
                masked_text=text,
                original_text=text,
                pii_detected=False,
                items_masked=0,
                mask_mapping={}
            )
        
        masked_text = text
        items_masked = 0
        mask_mapping = {}
        
        # Apply pattern-based masking
        masked_text, count, mapping = self._mask_emails(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_phones(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_ssns(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_dobs(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_mrns(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_addresses(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_facilities(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        masked_text, count, mapping = self._mask_names(masked_text)
        items_masked += count
        mask_mapping.update(mapping)
        
        return MaskingResult(
            masked_text=masked_text,
            original_text=text,
            pii_detected=items_masked > 0,
            items_masked=items_masked,
            mask_mapping=mask_mapping
        )
    
    def _mask_emails(self, text: str) -> tuple[str, int, dict]:
        """Mask email addresses."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            mapping[original] = "[EMAIL]"
            return "[EMAIL]"
        
        masked = self.PATTERNS["email"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_phones(self, text: str) -> tuple[str, int, dict]:
        """Mask phone numbers."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            mapping[original] = "[PHONE]"
            return "[PHONE]"
        
        masked = self.PATTERNS["phone"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_ssns(self, text: str) -> tuple[str, int, dict]:
        """Mask Social Security Numbers."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            mapping[original] = "[SSN]"
            return "[SSN]"
        
        masked = self.PATTERNS["ssn"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_dobs(self, text: str) -> tuple[str, int, dict]:
        """Mask dates of birth."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            # Keep the label but mask the date
            masked_version = re.sub(r'[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}', '[DOB]', original)
            mapping[original] = masked_version
            return masked_version
        
        masked = self.PATTERNS["dob"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_mrns(self, text: str) -> tuple[str, int, dict]:
        """Mask Medical Record Numbers."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            # Keep the label but mask the number
            masked_version = re.sub(r'[A-Z0-9]{6,12}', '[MRN]', original, flags=re.IGNORECASE)
            mapping[original] = masked_version
            return masked_version
        
        masked = self.PATTERNS["mrn"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_addresses(self, text: str) -> tuple[str, int, dict]:
        """Mask street addresses."""
        mapping = {}
        count = 0
        
        def replace(match):
            nonlocal count
            count += 1
            original = match.group(0)
            mapping[original] = "[ADDRESS]"
            return "[ADDRESS]"
        
        masked = self.PATTERNS["address"].sub(replace, text)
        return masked, count, mapping
    
    def _mask_facilities(self, text: str) -> tuple[str, int, dict]:
        """Mask hospital and facility names."""
        mapping = {}
        count = 0
        masked = text
        
        for indicator in self.FACILITY_INDICATORS:
            # Match facility names like "St. Mary's Hospital", "ABC Medical Center"
            pattern = re.compile(
                rf'\b(?:[A-Z][a-zA-Z\'\.]*\s+){{0,3}}{re.escape(indicator)}\b',
                re.IGNORECASE
            )
            
            def replace(match):
                nonlocal count
                count += 1
                original = match.group(0)
                mapping[original] = "[HOSPITAL]"
                return "[HOSPITAL]"
            
            masked = pattern.sub(replace, masked)
        
        return masked, count, mapping
    
    def _mask_names(self, text: str) -> tuple[str, int, dict]:
        """
        Mask patient and doctor names.
        
        This is a simplified implementation. In production, use NER models.
        """
        mapping = {}
        count = 0
        masked = text
        
        # Match names after common prefixes
        for prefix in self.NAME_PREFIXES:
            # Pattern: Prefix followed by 1-3 capitalized words
            pattern = re.compile(
                rf'{re.escape(prefix)}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}})',
                re.IGNORECASE
            )
            
            def replace(match):
                nonlocal count
                count += 1
                original = match.group(0)
                name_part = match.group(1)
                
                # Determine if doctor or patient
                if prefix.lower().startswith(("dr", "prof")):
                    mask = "[DOCTOR_NAME]"
                else:
                    mask = "[PATIENT_NAME]"
                
                masked_version = match.group(0).replace(name_part, mask)
                mapping[original] = masked_version
                return masked_version
            
            masked = pattern.sub(replace, masked)
        
        return masked, count, mapping
    
    def pseudonymize_id(self, original_id: str, salt: Optional[str] = None) -> str:
        """
        Create a pseudonymous ID from an original identifier.
        
        Args:
            original_id: The original identifier (e.g., patient ID).
            salt: Optional salt for the hash. Use consistent salt for reproducibility.
            
        Returns:
            A pseudonymous identifier that cannot be reversed.
        """
        salt = salt or "medical-assistant-default-salt"
        combined = f"{salt}:{original_id}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()
        # Return first 12 characters prefixed with 'P'
        return f"P{hash_value[:11].upper()}"
    
    def generate_document_id(self) -> str:
        """Generate a unique document ID."""
        return f"DOC-{uuid.uuid4().hex[:12].upper()}"
    
    def generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        return f"{document_id}-C{chunk_index:04d}"


# Global masker instance
_masker: Optional[PIIMasker] = None


def get_masker() -> PIIMasker:
    """Get the global PII masker instance."""
    global _masker
    if _masker is None:
        _masker = PIIMasker(enabled=settings.enable_pii_masking)
    return _masker


def mask_text(text: str) -> MaskingResult:
    """Convenience function to mask text using the global masker."""
    return get_masker().mask_text(text)


def pseudonymize_id(original_id: str) -> str:
    """Convenience function to pseudonymize an ID."""
    return get_masker().pseudonymize_id(original_id)
