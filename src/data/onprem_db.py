"""
On-Premises Database for Original (Unmasked) Patient Data.

This module stores the ORIGINAL patient data securely on-premises.
Only the record_id is shared with cloud systems.

Security:
- Original data NEVER leaves the hospital network
- Only record_id links to masked cloud data
- Clinicians can fetch original by record_id after AI processing
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class OnPremDatabase:
    """
    On-premises database for storing original (unmasked) patient records.
    
    Uses SQLite for local development.
    In production, this would be PostgreSQL/SQL Server on hospital network.
    """
    
    def __init__(self, db_path: str | Path = "data/onprem/patient_records.db"):
        """
        Initialize on-prem database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Main table for original patient records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patient_records (
                    record_id TEXT PRIMARY KEY,
                    patient_name TEXT,
                    patient_dob TEXT,
                    patient_ssn TEXT,
                    patient_phone TEXT,
                    patient_email TEXT,
                    patient_address TEXT,
                    doctor_name TEXT,
                    hospital_name TEXT,
                    insurance_provider TEXT,
                    medical_record_number TEXT,
                    original_data JSON,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit log for access tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT,
                    accessed_by TEXT,
                    access_type TEXT,
                    access_reason TEXT,
                    ip_address TEXT,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (record_id) REFERENCES patient_records(record_id)
                )
            """)
            
            # Index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_record_id 
                ON patient_records(record_id)
            """)
            
            conn.commit()
            logger.info(f"On-prem database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def store_original_records_batch(
        self,
        records: list[tuple[str, dict, str]],
    ) -> int:
        """
        Store multiple original records in a single transaction (FAST).
        
        Args:
            records: List of (record_id, original_data, source_file) tuples
            
        Returns:
            Number of records stored
        """
        if not records:
            return 0
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Prepare batch data
                batch_data = []
                for record_id, original_data, source_file in records:
                    patient_name = original_data.get("Name", original_data.get("name", ""))
                    patient_dob = original_data.get("DOB", original_data.get("Date of Birth", ""))
                    doctor_name = original_data.get("Doctor", original_data.get("doctor", ""))
                    hospital_name = original_data.get("Hospital", original_data.get("hospital", ""))
                    insurance = original_data.get("Insurance Provider", original_data.get("insurance_provider", ""))
                    
                    batch_data.append((
                        record_id,
                        patient_name,
                        patient_dob,
                        doctor_name,
                        hospital_name,
                        insurance,
                        json.dumps(original_data),
                        source_file,
                        datetime.now().isoformat(),
                    ))
                
                # Batch insert
                cursor.executemany("""
                    INSERT OR REPLACE INTO patient_records 
                    (record_id, patient_name, patient_dob, doctor_name, hospital_name, 
                     insurance_provider, original_data, source_file, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_data)
                
                conn.commit()
                return len(batch_data)
                
        except Exception as e:
            logger.error(f"Failed to batch store records: {e}")
            return 0
    
    def store_original_record(
        self,
        record_id: str,
        original_data: dict,
        source_file: str = "",
    ) -> bool:
        """
        Store original (unmasked) patient record.
        
        Args:
            record_id: Unique identifier (shared with cloud)
            original_data: Original unmasked patient data
            source_file: Source file name
            
        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Extract common PII fields for indexed access
                patient_name = original_data.get("Name", original_data.get("name", ""))
                patient_dob = original_data.get("DOB", original_data.get("Date of Birth", ""))
                doctor_name = original_data.get("Doctor", original_data.get("doctor", ""))
                hospital_name = original_data.get("Hospital", original_data.get("hospital", ""))
                insurance = original_data.get("Insurance Provider", original_data.get("insurance_provider", ""))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO patient_records 
                    (record_id, patient_name, patient_dob, doctor_name, hospital_name, 
                     insurance_provider, original_data, source_file, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id,
                    patient_name,
                    patient_dob,
                    doctor_name,
                    hospital_name,
                    insurance,
                    json.dumps(original_data),
                    source_file,
                    datetime.now().isoformat(),
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to store original record {record_id}: {e}")
            return False
    
    def get_original_record(
        self,
        record_id: str,
        accessed_by: str = "system",
        access_reason: str = "clinical_review",
    ) -> dict | None:
        """
        Retrieve original (unmasked) patient record.
        
        Args:
            record_id: Unique identifier
            accessed_by: User/system accessing the data (for audit)
            access_reason: Reason for access (for audit)
            
        Returns:
            Original patient data or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Log the access for audit trail
                cursor.execute("""
                    INSERT INTO access_log (record_id, accessed_by, access_type, access_reason)
                    VALUES (?, ?, 'READ', ?)
                """, (record_id, accessed_by, access_reason))
                
                # Fetch the record
                cursor.execute("""
                    SELECT * FROM patient_records WHERE record_id = ?
                """, (record_id,))
                
                row = cursor.fetchone()
                conn.commit()
                
                if row:
                    result = dict(row)
                    # Parse JSON data
                    if result.get("original_data"):
                        result["original_data"] = json.loads(result["original_data"])
                    return result
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get original record {record_id}: {e}")
            return None
    
    def get_original_by_ids(
        self,
        record_ids: list[str],
        accessed_by: str = "system",
    ) -> dict[str, dict]:
        """
        Retrieve multiple original records by IDs.
        
        Args:
            record_ids: List of record IDs
            accessed_by: User accessing the data
            
        Returns:
            Dictionary mapping record_id to original data
        """
        results = {}
        for record_id in record_ids:
            record = self.get_original_record(record_id, accessed_by)
            if record:
                results[record_id] = record.get("original_data", {})
        return results
    
    def get_access_log(self, record_id: str, limit: int = 100) -> list[dict]:
        """Get access audit log for a record."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM access_log 
                    WHERE record_id = ?
                    ORDER BY accessed_at DESC
                    LIMIT ?
                """, (record_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get access log: {e}")
            return []
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM patient_records")
                total_records = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM access_log")
                total_accesses = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM access_log 
                    WHERE accessed_at > datetime('now', '-24 hours')
                """)
                recent_accesses = cursor.fetchone()[0]
                
                return {
                    "total_records": total_records,
                    "total_accesses": total_accesses,
                    "accesses_last_24h": recent_accesses,
                    "database_path": str(self.db_path),
                    "database_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2) if self.db_path.exists() else 0,
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Global instance
_onprem_db: OnPremDatabase | None = None


def get_onprem_db() -> OnPremDatabase:
    """Get or create the on-prem database instance."""
    global _onprem_db
    if _onprem_db is None:
        db_path = os.getenv("ONPREM_DB_PATH", "data/onprem/patient_records.db")
        _onprem_db = OnPremDatabase(db_path)
    return _onprem_db
