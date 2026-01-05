"""
Data Processing Pipeline for Medical Assistant.

HYBRID ARCHITECTURE:
- On-Prem Database: Stores ORIGINAL (unmasked) patient data securely
- Cloud (Databricks/FAISS): Stores MASKED data only for AI processing

Data Layers:
- Bronze (raw/): Original unprocessed data from Kaggle
- Silver (processed/): Cleaned, validated, and PII-masked data  
- Gold (ai_ready/): Transformed data ready for RAG/AI processing

Security:
- Original PII never leaves on-prem database
- Only record_id links cloud data to on-prem original
- Clinicians retrieve original data using record_id after AI query

This module provides processing functions that can be called via API
or used directly for batch processing.
"""

import json
import hashlib
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any
import pandas as pd

from src.utils.masking import PIIMasker
from src.data.onprem_db import get_onprem_db


class DataProcessor:
    """
    Processes raw healthcare data through the Bronze → Silver → Gold pipeline.
    
    HYBRID ARCHITECTURE:
    - Stores ORIGINAL data in on-prem database (secure, never leaves hospital)
    - Stores MASKED data in cloud (Databricks, FAISS vector store)
    - Uses record_id to link masked → original for clinician access
    
    Responsibilities:
    - Load raw CSV/JSON files from Bronze layer
    - Generate unique record_id for each record
    - Store original in on-prem database
    - Apply PII masking and store in cloud-ready format
    - Transform to AI-ready format for Gold layer
    """
    
    def __init__(
        self,
        raw_dir: Path = Path("data/raw"),
        processed_dir: Path = Path("data/processed"),
        ai_ready_dir: Path = Path("data/ai_ready"),
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.ai_ready_dir = Path(ai_ready_dir)
        self.masker = PIIMasker()
        self.onprem_db = get_onprem_db()
        
        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.ai_ready_dir.mkdir(parents=True, exist_ok=True)
    
    def get_raw_datasets(self) -> list[dict]:
        """List all raw datasets available for processing."""
        datasets = []
        kaggle_dir = self.raw_dir / "kaggle"
        
        if not kaggle_dir.exists():
            return datasets
        
        for dataset_dir in kaggle_dir.iterdir():
            if not dataset_dir.is_dir():
                continue
            
            metadata_path = dataset_dir / "_metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                metadata["path"] = str(dataset_dir)
                datasets.append(metadata)
            else:
                # Create basic metadata from files
                files = [f.name for f in dataset_dir.glob("*.csv")]
                datasets.append({
                    "dataset_key": dataset_dir.name,
                    "path": str(dataset_dir),
                    "files": files,
                    "status": "raw",
                    "processed": False,
                })
        
        return datasets
    
    def get_processing_status(self) -> dict:
        """Get status of all data processing."""
        raw_datasets = self.get_raw_datasets()
        
        # Check processed datasets
        processed = []
        if self.processed_dir.exists():
            for f in self.processed_dir.glob("*.json"):
                try:
                    with open(f) as file:
                        data = json.load(file)
                        processed.append({
                            "file": f.name,
                            "records": len(data.get("records", [])),
                            "processed_at": data.get("processed_at"),
                        })
                except Exception:
                    pass
        
        # Check AI-ready data
        ai_ready = []
        if self.ai_ready_dir.exists():
            for f in self.ai_ready_dir.glob("*.json"):
                try:
                    with open(f) as file:
                        data = json.load(file)
                        ai_ready.append({
                            "file": f.name,
                            "documents": len(data.get("documents", [])),
                        })
                except Exception:
                    pass
        
        return {
            "raw_datasets": raw_datasets,
            "processed_files": processed,
            "ai_ready_files": ai_ready,
            "summary": {
                "raw_count": len(raw_datasets),
                "processed_count": len(processed),
                "ai_ready_count": len(ai_ready),
            }
        }
    
    def process_dataset(self, dataset_key: str) -> dict:
        """
        Process a single raw dataset through Silver and Gold layers.
        
        Args:
            dataset_key: Name of the dataset folder in raw/kaggle/
            
        Returns:
            Processing result with statistics
        """
        dataset_dir = self.raw_dir / "kaggle" / dataset_key
        
        if not dataset_dir.exists():
            return {
                "success": False,
                "error": f"Dataset not found: {dataset_key}",
            }
        
        # Load metadata
        metadata_path = dataset_dir / "_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
        else:
            metadata = {"dataset_key": dataset_key}
        
        # Find CSV files
        csv_files = list(dataset_dir.glob("*.csv"))
        if not csv_files:
            return {
                "success": False,
                "error": f"No CSV files found in {dataset_key}",
            }
        
        results = []
        for csv_file in csv_files:
            result = self._process_csv_file(csv_file, metadata)
            results.append(result)
        
        # Update metadata
        metadata["processed"] = True
        metadata["processed_at"] = datetime.now().isoformat()
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "dataset": dataset_key,
            "files_processed": len(results),
            "results": results,
        }
    
    def _process_csv_file(self, csv_path: Path, metadata: dict) -> dict:
        """
        Process a single CSV file through Silver and Gold layers.
        
        HYBRID STORAGE:
        1. Generate unique record_id (UUID) for each row
        2. Store ORIGINAL data in on-prem database with record_id
        3. Store MASKED data in Silver layer (cloud-ready) with record_id
        4. Transform to Gold layer documents for AI/RAG processing
        """
        
        try:
            df = pd.read_csv(csv_path, low_memory=False)
        except Exception as e:
            return {
                "file": csv_path.name,
                "success": False,
                "error": str(e),
            }
        
        original_count = len(df)
        contains_pii = metadata.get("contains_pii", True)
        
        # ===== SILVER LAYER: Store Original + Mask for Cloud =====
        silver_records = []
        onprem_stored = 0
        pii_stats = {
            "emails_masked": 0,
            "phones_masked": 0,
            "ssns_masked": 0,
            "names_masked": 0,
            "dates_masked": 0,
        }
        
        for idx, row in df.iterrows():
            record = row.to_dict()
            
            # Generate unique record_id (UUID format for better security)
            record_id = f"rec_{uuid.uuid4()}"
            
            # ===== STORE ORIGINAL IN ON-PREM DATABASE =====
            # This data NEVER leaves the hospital network
            original_data = {
                k: str(v) if pd.notna(v) else None 
                for k, v in record.items()
            }
            
            if self.onprem_db.store_original_record(
                record_id=record_id,
                original_data=original_data,
                source_file=csv_path.name,
            ):
                onprem_stored += 1
            
            # ===== CREATE MASKED RECORD FOR CLOUD =====
            masked_record = {}
            
            for col, value in record.items():
                if pd.isna(value):
                    masked_record[col] = None
                    continue
                
                # Convert to string for text columns
                str_value = str(value)
                
                if contains_pii:
                    # Apply masking
                    masked_value, mask_info = self._mask_value(str_value, col)
                    masked_record[col] = masked_value
                    
                    # Track stats
                    for key in mask_info:
                        if key in pii_stats:
                            pii_stats[key] += mask_info[key]
                else:
                    masked_record[col] = value
            
            # Add record_id (this links to on-prem original)
            masked_record["_record_id"] = record_id
            masked_record["_source_file"] = csv_path.name
            silver_records.append(masked_record)
        
        # Save Silver layer (MASKED data only - safe for cloud)
        silver_output = {
            "source": str(csv_path),
            "processed_at": datetime.now().isoformat(),
            "original_count": original_count,
            "record_count": len(silver_records),
            "pii_masking_applied": contains_pii,
            "pii_stats": pii_stats,
            "hybrid_storage": {
                "onprem_records_stored": onprem_stored,
                "cloud_records_stored": len(silver_records),
                "note": "Original data stored in on-prem DB, masked data in cloud"
            },
            "records": silver_records,
        }
        
        silver_path = self.processed_dir / f"{csv_path.stem}_silver.json"
        with open(silver_path, "w") as f:
            json.dump(silver_output, f, indent=2)
        
        # ===== GOLD LAYER: Transform to AI-ready documents =====
        gold_documents = self._transform_to_documents(silver_records, metadata)
        
        gold_output = {
            "source": str(silver_path),
            "created_at": datetime.now().isoformat(),
            "document_count": len(gold_documents),
            "documents": gold_documents,
        }
        
        gold_path = self.ai_ready_dir / f"{csv_path.stem}_gold.json"
        with open(gold_path, "w") as f:
            json.dump(gold_output, f, indent=2)
        
        return {
            "file": csv_path.name,
            "success": True,
            "original_records": original_count,
            "silver_records": len(silver_records),
            "gold_documents": len(gold_documents),
            "onprem_records_stored": onprem_stored,
            "pii_stats": pii_stats,
            "silver_path": str(silver_path),
            "gold_path": str(gold_path),
            "hybrid_storage": {
                "on_prem_db": str(self.onprem_db.db_path),
                "cloud_silver": str(silver_path),
                "cloud_gold": str(gold_path),
            }
        }
    
    def _mask_value(self, value: str, column: str) -> tuple[str, dict]:
        """Apply PII masking to a value and return stats."""
        stats = {
            "emails_masked": 0,
            "phones_masked": 0,
            "ssns_masked": 0,
            "names_masked": 0,
            "dates_masked": 0,
            "hospitals_masked": 0,
        }
        
        # Check for PII patterns before masking
        if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value):
            stats["emails_masked"] = 1
        if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', value):
            stats["phones_masked"] = 1
        if re.search(r'\b\d{3}[-]?\d{2}[-]?\d{4}\b', value):
            stats["ssns_masked"] = 1
        
        # Columns that contain names - mask entire value
        name_columns = ["name", "doctor", "patient", "provider", "physician"]
        if any(nc in column.lower() for nc in name_columns):
            stats["names_masked"] = 1
            return "[MASKED_NAME]", stats
        
        # Columns that contain hospital/facility names
        hospital_columns = ["hospital", "facility", "clinic", "center"]
        if any(hc in column.lower() for hc in hospital_columns):
            stats["hospitals_masked"] = 1
            return "[MASKED_HOSPITAL]", stats
        
        # Columns that contain insurance info
        insurance_columns = ["insurance", "insurer", "payer"]
        if any(ic in column.lower() for ic in insurance_columns):
            return "[MASKED_INSURANCE]", stats
        
        # Apply general masking for other columns
        masked_result = self.masker.mask_text(value)
        masked = masked_result.masked_text
        
        return masked, stats
    
    def _generate_record_id(self, idx: int, filename: str) -> str:
        """Generate a unique record ID."""
        hash_input = f"{filename}:{idx}:{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _transform_to_documents(
        self, 
        records: list[dict], 
        metadata: dict
    ) -> list[dict]:
        """
        Transform Silver records into Gold AI-ready documents.
        
        Creates text documents suitable for RAG indexing.
        """
        documents = []
        dataset_type = metadata.get("type", "structured")
        
        for record in records:
            # Determine text content based on dataset type
            if dataset_type == "text":
                # Use existing text columns
                text = self._extract_text_content(record)
            else:
                # Convert structured data to narrative text
                text = self._structured_to_narrative(record)
            
            if not text or len(text.strip()) < 10:
                continue
            
            doc = {
                "id": record.get("_record_id", ""),
                "text": text,
                "source": record.get("_source_file", ""),
                "metadata": {
                    k: v for k, v in record.items() 
                    if not k.startswith("_") and k not in ["text", "content"]
                },
            }
            documents.append(doc)
        
        return documents
    
    def _extract_text_content(self, record: dict) -> str:
        """Extract text content from text-type records."""
        text_columns = [
            "clinical_note", "notes", "text", "content", 
            "pn_history", "description", "findings"
        ]
        
        for col in text_columns:
            if col in record and record[col]:
                return str(record[col])
        
        return ""
    
    def _structured_to_narrative(self, record: dict) -> str:
        """Convert structured record to narrative text for RAG."""
        parts = []
        
        # Build narrative from available fields
        if "Medical Condition" in record and record["Medical Condition"]:
            parts.append(f"Diagnosis: {record['Medical Condition']}")
        
        if "Medication" in record and record["Medication"]:
            parts.append(f"Medication: {record['Medication']}")
        
        if "Test Results" in record and record["Test Results"]:
            parts.append(f"Test Results: {record['Test Results']}")
        
        if "Admission Type" in record:
            parts.append(f"Admission: {record['Admission Type']}")
        
        # Add demographic info (already masked)
        demographics = []
        if "Age" in record:
            demographics.append(f"Age: {record['Age']}")
        if "Gender" in record:
            demographics.append(f"Gender: {record['Gender']}")
        if "Blood Type" in record:
            demographics.append(f"Blood Type: {record['Blood Type']}")
        
        if demographics:
            parts.append("Demographics: " + ", ".join(demographics))
        
        # For diabetes datasets
        if "Glucose" in record:
            metrics = []
            for field in ["Glucose", "BloodPressure", "BMI", "Insulin"]:
                if field in record and record[field]:
                    metrics.append(f"{field}: {record[field]}")
            if metrics:
                parts.append("Metrics: " + ", ".join(metrics))
        
        # For heart failure datasets
        if "ejection_fraction" in record:
            cardiac = []
            for field in ["ejection_fraction", "serum_creatinine", "platelets"]:
                if field in record and record[field]:
                    cardiac.append(f"{field}: {record[field]}")
            if cardiac:
                parts.append("Cardiac markers: " + ", ".join(cardiac))
        
        return ". ".join(parts) if parts else ""
    
    def process_all(self) -> dict:
        """Process all available raw datasets."""
        datasets = self.get_raw_datasets()
        
        if not datasets:
            return {
                "success": True,
                "message": "No raw datasets found to process",
                "datasets_processed": 0,
            }
        
        results = []
        for dataset in datasets:
            if dataset.get("processed"):
                results.append({
                    "dataset": dataset["dataset_key"],
                    "skipped": True,
                    "reason": "Already processed",
                })
                continue
            
            result = self.process_dataset(dataset["dataset_key"])
            results.append(result)
        
        return {
            "success": True,
            "datasets_processed": len([r for r in results if r.get("success")]),
            "datasets_skipped": len([r for r in results if r.get("skipped")]),
            "results": results,
        }


# Convenience functions for API
def get_processor() -> DataProcessor:
    """Get a DataProcessor instance with default paths."""
    return DataProcessor()


def process_all_data() -> dict:
    """Process all raw data through the pipeline."""
    return get_processor().process_all()


def process_dataset(dataset_key: str) -> dict:
    """Process a specific dataset."""
    return get_processor().process_dataset(dataset_key)


def get_data_status() -> dict:
    """Get current data pipeline status."""
    return get_processor().get_processing_status()
