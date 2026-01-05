#!/usr/bin/env python3
"""
Quick Hybrid Data Processor.

Processes Kaggle data with hybrid storage:
- Local SQLite: Original patient data (fast, immediate)
- Databricks: Synced for production (background)

This is optimized for speed - uses batch operations.

Usage:
    python3 scripts/quick_process.py
"""

import sys
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("🏥 Quick Hybrid Data Processor")
print("=" * 60)

# Paths
RAW_DIR = project_root / "data" / "raw" / "kaggle"
PROCESSED_DIR = project_root / "data" / "processed"
AI_READY_DIR = project_root / "data" / "ai_ready"
VECTOR_DIR = project_root / "data" / "vector_store"
ONPREM_DIR = project_root / "data" / "onprem"

# Ensure dirs
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
AI_READY_DIR.mkdir(parents=True, exist_ok=True)
ONPREM_DIR.mkdir(parents=True, exist_ok=True)

# Step 1: Clean
print("\n[1/4] Cleaning old data...")
for f in PROCESSED_DIR.glob("*.json"):
    f.unlink()
for f in AI_READY_DIR.glob("*.json"):
    f.unlink()
db_file = ONPREM_DIR / "patient_records.db"
if db_file.exists():
    db_file.unlink()
if VECTOR_DIR.exists():
    shutil.rmtree(VECTOR_DIR)
print("✓ Clean")

# Step 2: Process CSV files
print("\n[2/4] Processing CSV files...")

import pandas as pd
from src.data.onprem_db import OnPremDatabase
from src.utils.masking import PIIMasker

# Initialize
db = OnPremDatabase(str(db_file))
masker = PIIMasker()

# Column patterns for masking
def mask_value(value, col):
    if pd.isna(value):
        return None
    s = str(value)
    col_lower = col.lower()
    if any(x in col_lower for x in ["name", "doctor", "patient", "physician"]):
        return "[MASKED_NAME]"
    if any(x in col_lower for x in ["hospital", "facility", "clinic"]):
        return "[MASKED_HOSPITAL]"
    if any(x in col_lower for x in ["insurance", "insurer"]):
        return "[MASKED_INSURANCE]"
    return masker.mask_text(s).masked_text

def to_narrative(rec):
    parts = []
    if rec.get("Medical Condition"):
        parts.append(f"Diagnosis: {rec['Medical Condition']}")
    if rec.get("Medication"):
        parts.append(f"Medication: {rec['Medication']}")
    if rec.get("Admission Type"):
        parts.append(f"Admission: {rec['Admission Type']}")
    for f in ["Age", "Gender", "Blood Type"]:
        if rec.get(f):
            parts.append(f"{f}: {rec[f]}")
    return ". ".join(parts)

# Find CSVs
csv_files = list(RAW_DIR.glob("*/*.csv"))
print(f"  Found {len(csv_files)} CSV files")

total_original = 0
total_gold = 0

for csv_path in csv_files:
    print(f"\n  Processing: {csv_path.name}")
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as e:
        print(f"    ✗ Error: {e}")
        continue
    
    print(f"    Rows: {len(df)}")
    
    # Prepare batch data
    batch = []
    silver_records = []
    gold_docs = []
    
    for idx, row in df.iterrows():
        record_id = f"rec_{uuid.uuid4()}"
        original = {k: str(v) if pd.notna(v) else None for k, v in row.items()}
        
        # Batch for on-prem DB
        batch.append((record_id, original, csv_path.name))
        
        # Masked record
        masked = {k: mask_value(v, k) for k, v in row.items()}
        masked["_record_id"] = record_id
        masked["_source_file"] = csv_path.name
        silver_records.append(masked)
        
        # Gold doc
        text = to_narrative(masked)
        if text and len(text) >= 10:
            gold_docs.append({
                "id": record_id,
                "text": text,
                "source": csv_path.name,
                "metadata": {k: v for k, v in masked.items() if not k.startswith("_")},
            })
        
        # Batch insert every 5000
        if len(batch) >= 5000:
            db.store_original_records_batch(batch)
            total_original += len(batch)
            batch = []
            print(f"    ... stored {total_original} records")
    
    # Final batch
    if batch:
        db.store_original_records_batch(batch)
        total_original += len(batch)
    
    total_gold += len(gold_docs)
    print(f"    ✓ Original: {len(df)} | Gold: {len(gold_docs)}")
    
    # Save Silver
    silver_path = PROCESSED_DIR / f"{csv_path.stem}_silver.json"
    with open(silver_path, "w") as f:
        json.dump({"records": silver_records, "count": len(silver_records)}, f)
    
    # Save Gold
    gold_path = AI_READY_DIR / f"{csv_path.stem}_gold.json"
    with open(gold_path, "w") as f:
        json.dump({"documents": gold_docs, "document_count": len(gold_docs)}, f)

print(f"\n✓ Processed: {total_original} original, {total_gold} gold docs")

# Step 3: Check DB stats
print("\n[3/4] Database stats...")
stats = db.get_stats()
print(f"  Records: {stats.get('total_records', 0)}")
print(f"  Size: {stats.get('database_size_mb', 0)} MB")

# Step 4: Index vector store
print("\n[4/4] Indexing vector store...")

from src.rag.vector_store import VectorStore

# Create vector store and index gold documents
vector_store = VectorStore(persist_directory=str(VECTOR_DIR))

# Load all gold documents
all_docs = []
for gold_file in AI_READY_DIR.glob("*.json"):
    with open(gold_file) as f:
        data = json.load(f)
    for doc in data.get("documents", []):
        all_docs.append({
            "id": doc["id"],
            "content": doc["text"],
            "metadata": doc.get("metadata", {}),
            "source": doc.get("source", ""),
        })

print(f"  Adding {len(all_docs)} documents to vector store...")

# Add in batches
batch_size = 1000
for i in range(0, len(all_docs), batch_size):
    batch = all_docs[i:i+batch_size]
    texts = [d["content"] for d in batch]
    metadatas = [{"id": d["id"], "source": d["source"], **d["metadata"]} for d in batch]
    ids = [d["id"] for d in batch]
    vector_store.add_texts(texts, metadatas, ids)
    print(f"    ... indexed {min(i+batch_size, len(all_docs))} docs")

vector_store.save()
chunks_indexed = len(all_docs)
print(f"  ✓ Indexed {chunks_indexed} documents")

# Verify
print("\n" + "=" * 60)
print("✓ COMPLETE")
print("=" * 60)
print(f"  Local DB: {total_original} original records")
print(f"  FAISS: {chunks_indexed} masked documents")

# Test linkage
gold_files = list(AI_READY_DIR.glob("*.json"))
if gold_files:
    with open(gold_files[0]) as f:
        data = json.load(f)
    if data.get("documents"):
        test_id = data["documents"][0]["id"]
        original = db.get_original_record(test_id, "test", "verify")
        if original:
            print(f"\nLinkage test:")
            print(f"  Record ID: {test_id[:30]}...")
            print(f"  Patient: {original.get('patient_name', 'N/A')}")
            print(f"  Doctor: {original.get('doctor_name', 'N/A')}")
            print(f"  Hospital: {original.get('hospital_name', 'N/A')}")
            print("  ✓ Works!")

print("\nRestart backend to use new data.")
