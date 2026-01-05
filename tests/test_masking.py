"""Tests for PII masking utilities."""

import pytest

from src.utils.masking import PIIMasker, mask_text, pseudonymize_id


class TestPIIMasker:
    """Test cases for the PIIMasker class."""
    
    @pytest.fixture
    def masker(self):
        """Create a masker instance for testing."""
        return PIIMasker(enabled=True)
    
    def test_mask_email(self, masker):
        """Test that email addresses are masked."""
        text = "Contact the patient at john.doe@example.com for follow-up."
        result = masker.mask_text(text)
        
        assert "[EMAIL]" in result.masked_text
        assert "john.doe@example.com" not in result.masked_text
        assert result.pii_detected is True
        assert result.items_masked >= 1
    
    def test_mask_phone(self, masker):
        """Test that phone numbers are masked."""
        text = "Patient phone: (555) 123-4567. Emergency: 555-987-6543."
        result = masker.mask_text(text)
        
        assert "[PHONE]" in result.masked_text
        assert "555" not in result.masked_text or "[PHONE]" in result.masked_text
        assert result.pii_detected is True
    
    def test_mask_ssn(self, masker):
        """Test that SSNs are masked."""
        text = "Patient SSN: 123-45-6789"
        result = masker.mask_text(text)
        
        assert "[SSN]" in result.masked_text
        assert "123-45-6789" not in result.masked_text
        assert result.pii_detected is True
    
    def test_mask_address(self, masker):
        """Test that street addresses are masked."""
        text = "Patient lives at 123 Main Street, Apt 4B."
        result = masker.mask_text(text)
        
        assert "[ADDRESS]" in result.masked_text
        assert "123 Main Street" not in result.masked_text
    
    def test_mask_hospital(self, masker):
        """Test that hospital names are masked."""
        text = "Admitted to St. Mary's Hospital on Monday."
        result = masker.mask_text(text)
        
        assert "[HOSPITAL]" in result.masked_text
    
    def test_mask_dob(self, masker):
        """Test that dates of birth are masked."""
        text = "DOB: 05/15/1965. Patient is 60 years old."
        result = masker.mask_text(text)
        
        assert "[DOB]" in result.masked_text
        assert "05/15/1965" not in result.masked_text
    
    def test_mask_mrn(self, masker):
        """Test that Medical Record Numbers are masked."""
        text = "MRN: ABC123456789"
        result = masker.mask_text(text)
        
        assert "[MRN]" in result.masked_text
    
    def test_mask_patient_name(self, masker):
        """Test that patient names are masked."""
        text = "Patient: John Smith presented with symptoms."
        result = masker.mask_text(text)
        
        assert "[PATIENT_NAME]" in result.masked_text
    
    def test_mask_doctor_name(self, masker):
        """Test that doctor names are masked."""
        text = "Attending physician: Dr. Sarah Johnson"
        result = masker.mask_text(text)
        
        assert "[DOCTOR_NAME]" in result.masked_text
    
    def test_no_pii(self, masker):
        """Test that text without PII is not modified."""
        text = "HbA1c level was 7.2%. Continue metformin therapy."
        result = masker.mask_text(text)
        
        assert result.masked_text == text
        assert result.pii_detected is False
        assert result.items_masked == 0
    
    def test_disabled_masker(self):
        """Test that disabled masker doesn't mask anything."""
        masker = PIIMasker(enabled=False)
        text = "Email: test@example.com, Phone: 555-123-4567"
        result = masker.mask_text(text)
        
        assert result.masked_text == text
        assert result.pii_detected is False
    
    def test_multiple_pii(self, masker):
        """Test masking multiple PII items in one text."""
        text = """
        Patient: John Doe
        Email: john@email.com
        Phone: 555-123-4567
        SSN: 123-45-6789
        Admitted to City General Hospital
        """
        result = masker.mask_text(text)
        
        assert "[PATIENT_NAME]" in result.masked_text
        assert "[EMAIL]" in result.masked_text
        assert "[PHONE]" in result.masked_text
        assert "[SSN]" in result.masked_text
        assert "[HOSPITAL]" in result.masked_text
        assert result.items_masked >= 5


class TestPseudonymization:
    """Test cases for ID pseudonymization."""
    
    def test_pseudonymize_id_consistency(self):
        """Test that same ID produces same pseudonym."""
        id1 = pseudonymize_id("patient_123")
        id2 = pseudonymize_id("patient_123")
        
        assert id1 == id2
    
    def test_pseudonymize_id_uniqueness(self):
        """Test that different IDs produce different pseudonyms."""
        id1 = pseudonymize_id("patient_123")
        id2 = pseudonymize_id("patient_456")
        
        assert id1 != id2
    
    def test_pseudonymize_id_format(self):
        """Test that pseudonym has expected format."""
        result = pseudonymize_id("test_id")
        
        assert result.startswith("P")
        assert len(result) == 12  # 'P' + 11 characters


class TestMaskTextConvenience:
    """Test the convenience mask_text function."""
    
    def test_mask_text_function(self):
        """Test the module-level mask_text function."""
        text = "Contact: test@example.com"
        result = mask_text(text)
        
        assert "[EMAIL]" in result.masked_text
