#!/usr/bin/env python3
"""
Migrate 55,500 clinical records to Databricks Unity Catalog.

Architecture:
- clinical_records_masked: Full records with PII masked (safe for all users)
- pii_lookup: Original PII values only with record_id (clinicians with access)

When clinician queries, system joins by record_id to show unmasked data.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hvac
from databricks import sql as databricks_sql

# Configuration
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "dev-token-medical")
BATCH_SIZE = 500  # Records per batch insert

def get_vault_secrets():
    """Fetch Databricks credentials from Vault."""
    print("🔐 Fetching credentials from Vault...")
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    
    secret = client.secrets.kv.v2.read_secret_version(
        path="medical-assistant",
        mount_point="secret",
        raise_on_deleted_version=False
    )
    data = secret["data"]["data"]
    
    # Warehouse ID is hardcoded (or can be fetched from env)
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "78042e5b1a2be3e6")
    
    return {
        "host": data["DATABRICKS_HOST"].replace("https://", "").replace("http://", ""),
        "http_path": f"/sql/1.0/warehouses/{warehouse_id}",
        "access_token": data["DATABRICKS_TOKEN"]  # Using DATABRICKS_TOKEN key
    }


def get_databricks_connection(creds):
    """Create Databricks SQL connection."""
    return databricks_sql.connect(
        server_hostname=creds["host"],
        http_path=creds["http_path"],
        access_token=creds["access_token"]
    )


def ensure_tables_exist(cursor, drop_all=False):
    """Create catalog, schema, and tables if they don't exist."""
    print("📦 Ensuring tables exist...")
    
    # Create catalog (may fail if exists - that's ok)
    try:
        cursor.execute("CREATE CATALOG IF NOT EXISTS medical_ai")
        print("  ✓ Catalog 'medical_ai' ready")
    except Exception as e:
        print(f"  ⚠ Catalog note: {e}")
    
    # Use catalog
    cursor.execute("USE CATALOG medical_ai")
    
    # Create schema
    cursor.execute("CREATE SCHEMA IF NOT EXISTS clinical_data")
    print("  ✓ Schema 'clinical_data' ready")
    cursor.execute("USE SCHEMA clinical_data")
    
    if drop_all:
        # Drop existing tables to start fresh
        print("  🗑️ Dropping existing tables for fresh migration...")
        cursor.execute("DROP TABLE IF EXISTS clinical_records_masked")
        cursor.execute("DROP TABLE IF EXISTS pii_lookup")
    else:
        # Only recreate masked table
        print("  🗑️ Dropping only clinical_records_masked...")
        cursor.execute("DROP TABLE IF EXISTS clinical_records_masked")
    
    # Table 1: Clinical Records (Masked) - Full records, safe for everyone
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_records_masked (
            record_id STRING NOT NULL,
            clinical_text STRING,
            diagnosis STRING,
            medication STRING,
            admission_type STRING,
            age INT,
            gender STRING,
            blood_type STRING,
            date_of_admission STRING,
            discharge_date STRING,
            billing_amount STRING,
            room_number STRING,
            test_results STRING,
            source_file STRING,
            created_at TIMESTAMP,
            PRIMARY KEY (record_id)
        )
    """)
    print("  ✓ Table 'clinical_records_masked' created")
    
    if drop_all:
        # Table 2: PII Lookup (Unmasked) - Only PII values, clinicians only
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pii_lookup (
                record_id STRING NOT NULL,
                patient_name STRING,
                doctor_name STRING,
                hospital_name STRING,
                insurance_provider STRING,
                created_at TIMESTAMP,
                PRIMARY KEY (record_id)
            )
        """)
        print("  ✓ Table 'pii_lookup' created")
    
    # Create view for clinician access (joined view)
    cursor.execute("DROP VIEW IF EXISTS clinical_records_full")
    cursor.execute("""
        CREATE VIEW clinical_records_full AS
        SELECT 
            m.record_id,
            p.patient_name,
            p.doctor_name,
            p.hospital_name,
            p.insurance_provider,
            m.clinical_text,
            m.diagnosis,
            m.medication,
            m.admission_type,
            m.age,
            m.gender,
            m.blood_type,
            m.date_of_admission,
            m.discharge_date,
            m.billing_amount,
            m.room_number,
            m.test_results,
            m.source_file,
            m.created_at
        FROM clinical_records_masked m
        LEFT JOIN pii_lookup p ON m.record_id = p.record_id
    """)
    print("  ✓ View 'clinical_records_full' created (for clinicians)")


def load_masked_records():
    """Load all masked clinical records from ai_ready directory."""
    print("📄 Loading masked clinical records...")
    
    ai_ready_path = Path(__file__).parent.parent / "data" / "ai_ready"
    records = []
    
    files = list(ai_ready_path.glob("*.json"))
    print(f"  Found {len(files)} JSON files")
    
    for file_path in files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Handle wrapper structure with 'documents' key
            if isinstance(data, dict) and 'documents' in data:
                records.extend(data['documents'])
            elif isinstance(data, list):
                records.extend(data)
            else:
                records.append(data)
    
    print(f"  ✓ Loaded {len(records)} masked records")
    return records


def load_pii_mappings():
    """Load PII mappings from local SQLite database."""
    print("🔒 Loading PII mappings from local database...")
    
    db_path = Path(__file__).parent.parent / "data" / "pii" / "pii_mapping.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT record_id, patient_name, doctor_name, hospital_name, insurance_provider, created_at
        FROM pii_mapping
    """)
    
    mappings = {}
    for row in cursor.fetchall():
        mappings[row[0]] = {
            "patient_name": row[1],
            "doctor_name": row[2],
            "hospital_name": row[3],
            "insurance_provider": row[4],
            "created_at": row[5]
        }
    
    conn.close()
    print(f"  ✓ Loaded {len(mappings)} PII mappings")
    return mappings


def escape_sql(value):
    """Escape single quotes in SQL string values."""
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


def migrate_masked_records(cursor, records):
    """Migrate masked clinical records to Databricks."""
    print(f"📤 Migrating {len(records)} masked records to Databricks...")
    
    total = len(records)
    migrated = 0
    errors = 0
    
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        
        values_list = []
        for record in batch:
            metadata = record.get("metadata", {})
            
            values = (
                escape_sql(record.get("id")),
                escape_sql(record.get("text")),
                escape_sql(metadata.get("Medical Condition")),
                escape_sql(metadata.get("Medication")),
                escape_sql(metadata.get("Admission Type")),
                metadata.get("Age", "NULL"),
                escape_sql(metadata.get("Gender")),
                escape_sql(metadata.get("Blood Type")),
                escape_sql(metadata.get("Date of Admission")),
                escape_sql(metadata.get("Discharge Date")),
                escape_sql(metadata.get("Billing Amount")),
                escape_sql(metadata.get("Room Number")),
                escape_sql(metadata.get("Test Results")),
                escape_sql(record.get("source")),
                f"CURRENT_TIMESTAMP()"
            )
            values_list.append(f"({', '.join(str(v) for v in values)})")
        
        try:
            sql = f"""
                INSERT INTO clinical_records_masked 
                (record_id, clinical_text, diagnosis, medication, admission_type, 
                 age, gender, blood_type, date_of_admission, discharge_date,
                 billing_amount, room_number, test_results, source_file, created_at)
                VALUES {', '.join(values_list)}
            """
            cursor.execute(sql)
            migrated += len(batch)
            
            progress = (migrated / total) * 100
            print(f"  Progress: {migrated:,}/{total:,} ({progress:.1f}%)")
            
        except Exception as e:
            errors += len(batch)
            print(f"  ⚠ Error in batch: {str(e)[:100]}")
    
    print(f"  ✓ Masked records migrated: {migrated:,} success, {errors:,} errors")
    return migrated, errors


def migrate_pii_lookup(cursor, pii_mappings):
    """Migrate PII lookup table to Databricks."""
    print(f"📤 Migrating {len(pii_mappings)} PII records to Databricks...")
    
    total = len(pii_mappings)
    migrated = 0
    errors = 0
    
    items = list(pii_mappings.items())
    
    for i in range(0, total, BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        
        values_list = []
        for record_id, pii in batch:
            values = (
                escape_sql(record_id),
                escape_sql(pii.get("patient_name")),
                escape_sql(pii.get("doctor_name")),
                escape_sql(pii.get("hospital_name")),
                escape_sql(pii.get("insurance_provider")),
                f"CURRENT_TIMESTAMP()"
            )
            values_list.append(f"({', '.join(str(v) for v in values)})")
        
        try:
            sql = f"""
                INSERT INTO pii_lookup 
                (record_id, patient_name, doctor_name, hospital_name, insurance_provider, created_at)
                VALUES {', '.join(values_list)}
            """
            cursor.execute(sql)
            migrated += len(batch)
            
            progress = (migrated / total) * 100
            print(f"  Progress: {migrated:,}/{total:,} ({progress:.1f}%)")
            
        except Exception as e:
            errors += len(batch)
            print(f"  ⚠ Error in batch: {str(e)[:100]}")
    
    print(f"  ✓ PII records migrated: {migrated:,} success, {errors:,} errors")
    return migrated, errors


def verify_migration(cursor):
    """Verify migration by counting records in each table."""
    print("\n📊 Verifying migration...")
    
    cursor.execute("SELECT COUNT(*) FROM clinical_records_masked")
    masked_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pii_lookup")
    pii_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM clinical_records_full")
    full_count = cursor.fetchone()[0]
    
    print(f"  clinical_records_masked: {masked_count:,} records")
    print(f"  pii_lookup: {pii_count:,} records")
    print(f"  clinical_records_full (view): {full_count:,} records")
    
    # Show sample from joined view
    print("\n📋 Sample from clinical_records_full (clinician view):")
    cursor.execute("""
        SELECT record_id, patient_name, doctor_name, hospital_name, diagnosis, medication
        FROM clinical_records_full
        LIMIT 3
    """)
    
    for row in cursor.fetchall():
        print(f"  - {row[0][:20]}... | Patient: {row[1]} | Doctor: {row[2]} | Hospital: {row[3]} | Dx: {row[4]}")
    
    return masked_count, pii_count


def main():
    """Main migration function."""
    print("=" * 60)
    print("🏥 DATABRICKS MIGRATION: Clinical Records + PII Lookup")
    print("=" * 60)
    start_time = datetime.now()
    
    # Get credentials
    creds = get_vault_secrets()
    print(f"  ✓ Connected to: {creds['host']}")
    
    # Connect to Databricks
    print("\n🔌 Connecting to Databricks...")
    conn = get_databricks_connection(creds)
    cursor = conn.cursor()
    print("  ✓ Connected to Databricks SQL Warehouse")
    
    try:
        # Ensure tables exist (don't drop pii_lookup since it's already populated)
        ensure_tables_exist(cursor, drop_all=False)
        
        # Load data
        masked_records = load_masked_records()
        pii_mappings = load_pii_mappings()
        
        # Migrate data
        print("\n" + "=" * 60)
        masked_migrated, masked_errors = migrate_masked_records(cursor, masked_records)
        pii_migrated, pii_errors = migrate_pii_lookup(cursor, pii_mappings)
        
        # Verify
        verify_migration(cursor)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        print(f"  Masked records: {masked_migrated:,}")
        print(f"  PII records: {pii_migrated:,}")
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Tables: medical_ai.clinical_data.clinical_records_masked")
        print(f"          medical_ai.clinical_data.pii_lookup")
        print(f"  View:   medical_ai.clinical_data.clinical_records_full")
        print("\n  Access Control:")
        print("    - Analysts: clinical_records_masked (safe)")
        print("    - Clinicians: clinical_records_full (via join)")
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
