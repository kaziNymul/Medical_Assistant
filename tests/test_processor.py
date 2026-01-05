"""
Tests for the data processing pipeline.
"""

import json
import pytest
from pathlib import Path
import tempfile
import shutil

from src.data.processor import DataProcessor


@pytest.fixture
def temp_data_dirs():
    """Create temporary data directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir) / "raw" / "kaggle"
        processed_dir = Path(tmpdir) / "processed"
        ai_ready_dir = Path(tmpdir) / "ai_ready"
        
        raw_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        ai_ready_dir.mkdir(parents=True)
        
        yield {
            "raw": raw_dir.parent,
            "processed": processed_dir,
            "ai_ready": ai_ready_dir,
        }


@pytest.fixture
def sample_healthcare_csv(temp_data_dirs):
    """Create a sample healthcare CSV file."""
    raw_dir = temp_data_dirs["raw"]
    kaggle_dir = raw_dir / "kaggle" / "healthcare"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    
    csv_content = """Name,Age,Gender,Blood Type,Medical Condition,Medication,Doctor,Hospital,Insurance Provider,Admission Type,Date of Admission,Discharge Date,Test Results,Billing Amount
John Smith,45,Male,A+,Diabetes,Metformin,Dr. Sarah Johnson,Mayo Clinic,Blue Cross,Elective,2024-01-15,2024-01-20,Normal,15000.50
jane.doe@email.com,32,Female,O-,Hypertension,Lisinopril,Dr. Michael Brown,Cleveland Clinic,Aetna,Urgent,2024-02-01,2024-02-03,Abnormal,8500.00
Patient SSN 123-45-6789,67,Male,B+,Heart Disease,Aspirin,Dr. Emily Wilson,Johns Hopkins,United,Emergency,2024-02-10,2024-02-20,Inconclusive,45000.00
"""
    
    csv_path = kaggle_dir / "healthcare_dataset.csv"
    csv_path.write_text(csv_content)
    
    # Create metadata
    metadata = {
        "dataset_key": "healthcare",
        "type": "structured",
        "contains_pii": True,
        "fields": ["Name", "Age", "Gender", "Blood Type", "Medical Condition", 
                   "Medication", "Doctor", "Hospital"],
        "processed": False,
    }
    
    metadata_path = kaggle_dir / "_metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    
    return kaggle_dir


class TestDataProcessor:
    """Test the DataProcessor class."""
    
    def test_get_raw_datasets_empty(self, temp_data_dirs):
        """Test listing raw datasets when empty."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        datasets = processor.get_raw_datasets()
        assert datasets == []
    
    def test_get_raw_datasets_with_data(self, temp_data_dirs, sample_healthcare_csv):
        """Test listing raw datasets with data present."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        datasets = processor.get_raw_datasets()
        assert len(datasets) == 1
        assert datasets[0]["dataset_key"] == "healthcare"
        assert datasets[0]["contains_pii"] == True
    
    def test_get_processing_status(self, temp_data_dirs):
        """Test getting processing status."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        status = processor.get_processing_status()
        assert "raw_datasets" in status
        assert "processed_files" in status
        assert "ai_ready_files" in status
        assert "summary" in status
    
    def test_process_dataset(self, temp_data_dirs, sample_healthcare_csv):
        """Test processing a dataset through Silver and Gold layers."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        result = processor.process_dataset("healthcare")
        
        assert result["success"] == True
        assert result["dataset"] == "healthcare"
        assert result["files_processed"] == 1
        
        # Check Silver layer output
        silver_files = list(temp_data_dirs["processed"].glob("*_silver.json"))
        assert len(silver_files) == 1
        
        with open(silver_files[0]) as f:
            silver_data = json.load(f)
        
        assert "records" in silver_data
        assert len(silver_data["records"]) == 3
        assert silver_data["pii_masking_applied"] == True
        
        # Check Gold layer output
        gold_files = list(temp_data_dirs["ai_ready"].glob("*_gold.json"))
        assert len(gold_files) == 1
        
        with open(gold_files[0]) as f:
            gold_data = json.load(f)
        
        assert "documents" in gold_data
        assert len(gold_data["documents"]) > 0
    
    def test_pii_masking_applied(self, temp_data_dirs, sample_healthcare_csv):
        """Test that PII is properly masked in Silver layer."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        processor.process_dataset("healthcare")
        
        silver_files = list(temp_data_dirs["processed"].glob("*_silver.json"))
        with open(silver_files[0]) as f:
            silver_data = json.load(f)
        
        # Check that emails are masked
        all_content = json.dumps(silver_data["records"])
        assert "jane.doe@email.com" not in all_content
        assert "[EMAIL" in all_content or "@" not in all_content.lower()
    
    def test_process_nonexistent_dataset(self, temp_data_dirs):
        """Test processing a dataset that doesn't exist."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        result = processor.process_dataset("nonexistent")
        
        assert result["success"] == False
        assert "error" in result
    
    def test_process_all(self, temp_data_dirs, sample_healthcare_csv):
        """Test processing all datasets."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        result = processor.process_all()
        
        assert result["success"] == True
        assert result["datasets_processed"] == 1
    
    def test_gold_layer_document_format(self, temp_data_dirs, sample_healthcare_csv):
        """Test that Gold layer creates proper document format."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        processor.process_dataset("healthcare")
        
        gold_files = list(temp_data_dirs["ai_ready"].glob("*_gold.json"))
        with open(gold_files[0]) as f:
            gold_data = json.load(f)
        
        for doc in gold_data["documents"]:
            assert "id" in doc
            assert "text" in doc
            assert "source" in doc
            assert "metadata" in doc
            
            # Check text contains structured narrative
            assert len(doc["text"]) > 0


class TestDataProcessorIntegration:
    """Integration tests for the data processor."""
    
    def test_end_to_end_pipeline(self, temp_data_dirs, sample_healthcare_csv):
        """Test complete Bronze → Silver → Gold pipeline."""
        processor = DataProcessor(
            raw_dir=temp_data_dirs["raw"],
            processed_dir=temp_data_dirs["processed"],
            ai_ready_dir=temp_data_dirs["ai_ready"],
        )
        
        # Step 1: Check raw datasets
        raw = processor.get_raw_datasets()
        assert len(raw) == 1
        assert raw[0]["processed"] == False
        
        # Step 2: Process
        result = processor.process_dataset("healthcare")
        assert result["success"] == True
        
        # Step 3: Verify outputs exist
        assert list(temp_data_dirs["processed"].glob("*.json"))
        assert list(temp_data_dirs["ai_ready"].glob("*.json"))
        
        # Step 4: Check metadata updated
        metadata_path = temp_data_dirs["raw"] / "kaggle" / "healthcare" / "_metadata.json"
        with open(metadata_path) as f:
            metadata = json.load(f)
        assert metadata["processed"] == True
        assert "processed_at" in metadata
