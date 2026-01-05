#!/usr/bin/env python3
"""
FAST Re-process data with Hybrid Architecture.

Optimized for speed using:
- Batch SQLite inserts (1000 records at a time)
- Minimal console output
- Efficient pandas operations

Usage:
    python3 scripts/fast_hybrid_reprocess.py
"""

import sys
import json
import uuid
import shutil
import re
from pathlib import Path
from datetime import datetime

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("🏥 Hybrid Data Architecture - Fast Processor")
print("=" * 50)

# Directories
RAW_DIR = project_root / "data" / "raw" / "kaggle"
PROCESSED_DIR = project_root / "data" / "processed"
AI_READY_DIR = project_root / "data" / "ai_ready"
ONPREM_DIR = project_root / "data" / "onprem"
VECTOR_DIR = project_root / "data" / "vector_store"

# Create directories
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
AI_READY_DIR.mkdir(parents=True, exist_ok=True)
ONPREM_DIR.mkdir(parents=True, exist_ok=True)

# Step 1: Clean old data
print("\n[1/5] Cleaning old data...")
for f in PROCESSED_DIR.glob("*.json"):
    f.unlink()
for f in AI_READY_DIR.glob("*.json"):
    f.unlink()
if (ONPREM_DIR / "patient_records.db").exists():
    (ONPREM_DIR / "patient_records.db").unlink()
if VECTOR_DIR.exists():
    shutil.rmtree(VECTOR_DIR)
print("✓ Cleaned")

# Step 2: Reset metadata
print("\n[2/5] Resetting dataset metadata...")
for metadata_file in RAW_DIR.glob("*/_metadata.json"):
    with open(metadata_file) as f:
        metadata = json.load(f)
    metadata["processed"] = False
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
print("✓ Reset")

# Step 3: Process datasets
print("\n[3/5] Processing datasets with hybrid storage...")

from src.data.onprem_db import get_onprem_db
from src.utils.masking import PIIMasker

db = get_onprem_db()
masker = PIIMasker()

# PII column patterns
NAME_COLS = ["name", "doctor", "patient", "provider", "physician"]
HOSPITAL_COLS = ["hospital", "facility", "clinic", "center"]
INSURANCE_COLS = ["insurance", "insurer", "payer"]

def is_name_column(col):
    return any(nc in col.lower() for nc in NAME_COLS)

def is_hospital_column(col):
    return any(hc in col.lower() for hc in HOSPITAL_COLS)

def is_insurance_column(col):
    return any(ic in col.lower() for ic in INSURANCE_COLS)

def mask_value(value, col, masker_obj):
    """Fast masking."""
    if pd.isna(value):
        return None
    str_val = str(value)
    if is_name_column(col):
        return "[MASKED_NAME]"
    if is_hospital_column(col):
        return "[MASKED_HOSPITAL]"
    if is_insurance_column(col):
        return "[MASKED_INSURANCE]"
    return masker_obj.mask_text(str_val).masked_text

def structured_to_narrative(record):
    """Convert structured record to text."""
    parts = []
    if record.get("Medical Condition"):
        parts.append(f"Diagnosis: {record['Medical Condition']}")
    if record.get("Medication"):
        parts.append(f"Medication: {record['Medication']}")
    if record.get("Test Results"):
        parts.append(f"Test Results: {record['Test Results']}")
    if record.get("Admission Type"):
        parts.append(f"Admission: {record['Admission Type']}")
    
    demographics = []
    for f in ["Age", "Gender", "Blood Type"]:
        if record.get(f):
            demographics.append(f"{f}: {record[f]}")
    if demographics:
        parts.append("Demographics: " + ", ".join(demographics))
    
    # Diabetes metrics
    metrics = []
    for f in ["Glucose", "BloodPressure", "BMI", "Insulin"]:
        if record.get(f):
            metrics.append(f"{f}: {record[f]}")
    if metrics:
        parts.append("Metrics: " + ", ".join(metrics))
    
    return ". ".join(parts) if parts else ""

total_onprem = 0
total_cloud = 0
total_gold = 0

# Find all CSV files
csv_files = list(RAW_DIR.glob("*/*.csv"))
print(f"  Found {len(csv_files)} CSV files")

for csv_path in csv_files:
    print(f"\n  Processing: {csv_path.name}...")
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as e:
        print(f"    ✗ Error: {e}")
        continue
    
    print(f"    Rows: {len(df)}")
    
    # Generate record IDs for all rows at once
    record_ids = [f"rec_{uuid.uuid4()}" for _ in range(len(df))]
    
    # Prepare batch for on-prem storage
    onprem_batch = []
    silver_records = []
    
    for idx, (_, row) in enumerate(df.iterrows()):
        record_id = record_ids[idx]
        original = {k: str(v) if pd.notna(v) else None for k, v in row.to_dict().items()}
        
        # Add to on-prem batch
        onprem_batch.append((record_id, original, csv_path.name))
        
        # Create masked record
        masked = {}
        for col, value in row.to_dict().items():
            masked[col] = mask_value(value, col, masker)
        masked["_record_id"] = record_id
        masked["_source_file"] = csv_path.name
        silver_records.append(masked)
        
        # Batch insert every 1000 records
        if len(onprem_batch) >= 1000:
            db.store_original_records_batch(onprem_batch)
            total_onprem += len(onprem_batch)
            onprem_batch = []
    
    # Insert remaining
    if onprem_batch:
        db.store_original_records_batch(onprem_batch)
        total_onprem += len(onprem_batch)
    
    total_cloud += len(silver_records)
    print(f"    ✓ On-prem: {len(record_ids)} | Cloud: {len(silver_records)}")
    
    # Save Silver layer
    silver_output = {
        "source": str(csv_path),
        "processed_at": datetime.now().isoformat(),
        "record_count": len(silver_records),
        "records": silver_records,
    }
    silver_path = PROCESSED_DIR / f"{csv_path.stem}_silver.json"
    with open(silver_path, "w") as f:
        json.dump(silver_output, f)
    
    # Create Gold documents
    gold_docs = []
    for rec in silver_records:
        text = structured_to_narrative(rec)
        if text and len(text.strip()) >= 10:
            gold_docs.append({
                "id": rec["_record_id"],
                "text": text,
                "source": rec["_source_file"],
                "metadata": {k: v for k, v in rec.items() if not k.startswith("_")},
            })
    
    total_gold += len(gold_docs)
    
    gold_output = {
        "source": str(silver_path),
        "created_at": datetime.now().isoformat(),
        "document_count": len(gold_docs),
        "documents": gold_docs,
    }
    gold_path = AI_READY_DIR / f"{csv_path.stem}_gold.json"
    with open(gold_path, "w") as f:
        json.dump(gold_output, f)
    
    print(f"    ✓ Gold docs: {len(gold_docs)}")

print(f"\n✓ Processing complete!")
print(f"  On-prem records: {total_onprem}")
print(f"  Cloud records: {total_cloud}")
print(f"  Gold documents: {total_gold}")

# Step 4: On-prem stats
print("\n[4/5] On-Prem Database stats...")
stats = db.get_stats()
print(f"  Total records: {stats.get('total_records', 0)}")
print(f"  Database size: {stats.get('database_size_mb', 0)} MB")

# Step 5: Re-index vector store
print("\n[5/5] Indexing vector store...")

from src.rag.pipeline import RAGPipeline

pipeline = RAGPipeline(
    data_dir=str(AI_READY_DIR),
    index_path=str(VECTOR_DIR),
)
result = pipeline.index_documents()
print(f"  ✓ Indexed {result['chunks_indexed']} chunks")

# Verification
print("\n" + "=" * 50)
print("✓ HYBRID ARCHITECTURE SETUP COMPLETE")
print("=" * 50)
print(f"  On-Prem DB: {total_onprem} original records (secure)")
print(f"  Cloud FAISS: {result['chunks_indexed']} masked chunks")
print("\nTest record linkage:")

# Quick test
gold_files = list(AI_READY_DIR.glob("*.json"))
if gold_files:
    with open(gold_files[0]) as f:
        data = json.load(f)
    if data.get("documents"):
        test_id = data["documents"][0]["id"]
        original = db.get_original_record(test_id, "test", "verify")
        if original:
            print(f"  Record ID: {test_id}")
            print(f"  Original Name: {original.get('patient_name', 'N/A')}")
            print(f"  Original Doctor: {original.get('doctor_name', 'N/A')}")
            print("  ✓ Linkage works!")
        else:
            print("  ⚠ Could not verify linkage")

print("\nDone! Restart the backend server to use new data.")
