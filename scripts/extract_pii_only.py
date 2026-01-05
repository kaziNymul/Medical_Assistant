#!/usr/bin/env python3
"""
Optimized PII Reprocessing Script.

This script:
1. Reads existing masked JSON documents
2. Extracts ONLY PII fields (Name, Doctor, Hospital, Insurance)
3. Stores minimal PII in the new lightweight database
4. Links via record_id to cloud medical data

Result: Much smaller on-prem database (~5-8 MB vs 42 MB)
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.pii_db import get_pii_db


def extract_original_from_masked(masked_content: str) -> dict:
    """
    Reverse engineer original PII from masked content.
    
    Since masked content has patterns like [NAME_XXXX], we need the
    original data. We'll look for it in the JSON metadata or re-parse.
    """
    # PII fields we want to extract
    original_data = {}
    
    # Look for patterns that might contain original values
    # These would have been stored in the original CSV
    return original_data


def reprocess_from_csv():
    """Extract PII from existing old database into optimized PII-only database."""
    
    old_db_path = Path("data/onprem/patient_records.db")
    
    if not old_db_path.exists():
        print(f"❌ Old database not found: {old_db_path}")
        return
    
    print("=" * 60)
    print("OPTIMIZED PII EXTRACTION")
    print("=" * 60)
    print(f"\nSource: {old_db_path}")
    print()
    
    # Initialize PII database
    pii_db = get_pii_db()
    print(f"📁 New PII Database: {pii_db.db_path}")
    
    # Read from old database
    import sqlite3
    
    conn = sqlite3.connect(str(old_db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM patient_records")
    total_count = cursor.fetchone()[0]
    print(f"📊 Total records in old DB: {total_count:,}")
    
    # Batch extract PII
    print(f"\n🔄 Extracting PII fields only...")
    
    batch_size = 1000
    total_stored = 0
    offset = 0
    
    start_time = datetime.now()
    
    while True:
        cursor.execute(f"""
            SELECT record_id, patient_name, doctor_name, hospital_name, 
                   insurance_provider, source_file
            FROM patient_records 
            LIMIT {batch_size} OFFSET {offset}
        """)
        rows = cursor.fetchall()
        
        if not rows:
            break
        
        # Direct insert - no need to extract, these are already the PII fields
        batch_records = []
        for row in rows:
            original_data = {
                "Name": row["patient_name"],
                "Doctor": row["doctor_name"],
                "Hospital": row["hospital_name"],
                "Insurance Provider": row["insurance_provider"],
            }
            batch_records.append((row["record_id"], original_data, row["source_file"]))
        
        stored = pii_db.store_pii_batch(batch_records)
        total_stored += stored
        offset += batch_size
        print(f"  ✓ Migrated {total_stored:,} PII records...", end='\r')
    
    conn.close()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n\n{'=' * 60}")
    print("✅ PII EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Records migrated: {total_stored:,}")
    print(f"Time: {elapsed:.1f} seconds")
    
    # Show stats
    stats = pii_db.get_stats()
    print(f"\n📊 New Database Stats:")
    print(f"   Path: {stats['database_path']}")
    print(f"   Size: {stats['database_size_mb']:.2f} MB")
    print(f"   Type: {stats['storage_type']}")
    
    # Compare with old database
    old_size = old_db_path.stat().st_size / (1024 * 1024)
    new_size = stats['database_size_mb']
    savings = old_size - new_size
    percent = (savings / old_size) * 100 if old_size > 0 else 0
    
    print(f"\n📉 Storage Savings:")
    print(f"   Old database: {old_size:.1f} MB (stored all 15+ fields)")
    print(f"   New PII-only: {new_size:.1f} MB (stores only 4 PII fields)")
    print(f"   Savings: {savings:.1f} MB ({percent:.0f}%)")
    
    # Show sample
    print(f"\n📋 Sample PII Record:")
    sample = pii_db.get_pii(
        "rec_8b08670c-531c-426a-8cfa-3bd1a547b651", 
        accessed_by="script", 
        access_reason="verification"
    )
    if sample:
        for k, v in sample.items():
            print(f"   {k}: {v}")
    else:
        print("   (No sample available)")


if __name__ == "__main__":
    reprocess_from_csv()
