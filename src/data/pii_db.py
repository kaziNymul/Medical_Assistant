"""
Optimized PII-Only Database.

Stores ONLY the personal identifiable information (PII) that was masked.
This keeps the on-prem database small and efficient.

What's stored here (PII only):
- record_id (links to cloud data)
- patient_name
- doctor_name  
- hospital_name
- insurance_provider

What's NOT stored here (stays in cloud):
- Medical conditions, diagnoses
- Medications, test results
- Age, gender, blood type
- Admission info, billing
- Any other non-PII data
"""

import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PIIDatabase:
    """
    Lightweight database storing ONLY PII fields.
    
    This is much smaller than storing full records because:
    - Only 4-5 fields per record vs 15+ fields
    - No JSON blob storage
    - Estimated size: ~5-8 MB for 55,500 records (vs 42 MB previously)
    """
    
    # Fields that contain PII and need secure local storage
    PII_FIELDS = {
        "name": ["name", "patient_name", "patient"],
        "doctor": ["doctor", "physician", "provider", "doctor_name"],
        "hospital": ["hospital", "facility", "clinic", "hospital_name", "center"],
        "insurance": ["insurance", "insurer", "payer", "insurance_provider"],
    }
    
    def __init__(self, db_path: str | Path = "data/pii/pii_mapping.db"):
        """Initialize PII database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create optimized schema - PII fields only."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Lean PII table - only stores masked fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pii_mapping (
                    record_id TEXT PRIMARY KEY,
                    patient_name TEXT,
                    doctor_name TEXT,
                    hospital_name TEXT,
                    insurance_provider TEXT,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Access audit log for HIPAA compliance
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT,
                    accessed_by TEXT,
                    access_reason TEXT,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pii_record_id 
                ON pii_mapping(record_id)
            """)
            
            conn.commit()
            logger.info(f"PII database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def extract_pii_fields(self, original_data: dict) -> dict:
        """
        Extract only PII fields from a full record.
        
        Args:
            original_data: Full original record with all fields
            
        Returns:
            Dictionary with only PII fields
        """
        pii = {
            "patient_name": None,
            "doctor_name": None,
            "hospital_name": None,
            "insurance_provider": None,
        }
        
        # Direct field mapping (case-insensitive)
        for key, value in original_data.items():
            if value is None:
                continue
            
            key_lower = key.lower().strip()
            value_str = str(value).strip()
            
            # Map specific fields
            if key_lower in ["name", "patient_name", "patient"]:
                pii["patient_name"] = value_str
            elif key_lower in ["doctor", "doctor_name", "physician", "provider"]:
                pii["doctor_name"] = value_str
            elif key_lower in ["hospital", "hospital_name", "facility", "clinic"]:
                pii["hospital_name"] = value_str
            elif key_lower in ["insurance", "insurance provider", "insurance_provider", "insurer", "payer"]:
                pii["insurance_provider"] = value_str
        
        return pii
    
    def store_pii(
        self,
        record_id: str,
        original_data: dict,
        source_file: str = "",
    ) -> bool:
        """
        Store only PII fields from a record.
        
        Args:
            record_id: Unique identifier
            original_data: Full original record
            source_file: Source file name
            
        Returns:
            True if successful
        """
        try:
            pii = self.extract_pii_fields(original_data)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO pii_mapping 
                    (record_id, patient_name, doctor_name, hospital_name, 
                     insurance_provider, source_file, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id,
                    pii["patient_name"],
                    pii["doctor_name"],
                    pii["hospital_name"],
                    pii["insurance_provider"],
                    source_file,
                    datetime.now().isoformat(),
                ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to store PII for {record_id}: {e}")
            return False
    
    def store_pii_batch(self, records: list[tuple[str, dict, str]]) -> int:
        """
        Batch store PII for multiple records (fast).
        
        Args:
            records: List of (record_id, original_data, source_file)
            
        Returns:
            Number of records stored
        """
        if not records:
            return 0
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                batch_data = []
                for record_id, original_data, source_file in records:
                    pii = self.extract_pii_fields(original_data)
                    batch_data.append((
                        record_id,
                        pii["patient_name"],
                        pii["doctor_name"],
                        pii["hospital_name"],
                        pii["insurance_provider"],
                        source_file,
                        datetime.now().isoformat(),
                    ))
                
                cursor.executemany("""
                    INSERT OR REPLACE INTO pii_mapping 
                    (record_id, patient_name, doctor_name, hospital_name, 
                     insurance_provider, source_file, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batch_data)
                
                conn.commit()
                return len(batch_data)
                
        except Exception as e:
            logger.error(f"Failed to batch store PII: {e}")
            return 0
    
    def get_pii(
        self,
        record_id: str,
        accessed_by: str = "system",
        access_reason: str = "clinical_review",
    ) -> dict | None:
        """
        Get PII for a record.
        
        Args:
            record_id: Unique identifier
            accessed_by: Who is accessing (for audit)
            access_reason: Why (for audit)
            
        Returns:
            PII data or None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Log access for HIPAA
                cursor.execute("""
                    INSERT INTO access_log (record_id, accessed_by, access_reason)
                    VALUES (?, ?, ?)
                """, (record_id, accessed_by, access_reason))
                
                # Get PII
                cursor.execute("""
                    SELECT * FROM pii_mapping WHERE record_id = ?
                """, (record_id,))
                
                row = cursor.fetchone()
                conn.commit()
                
                if row:
                    return {
                        "record_id": row["record_id"],
                        "patient_name": row["patient_name"],
                        "doctor_name": row["doctor_name"],
                        "hospital_name": row["hospital_name"],
                        "insurance_provider": row["insurance_provider"],
                        "source_file": row["source_file"],
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get PII for {record_id}: {e}")
            return None
    
    def get_pii_batch(self, record_ids: list[str], accessed_by: str = "system") -> dict:
        """Get PII for multiple records."""
        results = {}
        for record_id in record_ids:
            pii = self.get_pii(record_id, accessed_by)
            if pii:
                results[record_id] = pii
        return results
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM pii_mapping")
                total = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM access_log")
                accesses = cursor.fetchone()[0]
                
                size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
                
                return {
                    "total_records": total,
                    "total_accesses": accesses,
                    "database_path": str(self.db_path),
                    "database_size_mb": round(size_mb, 2),
                    "storage_type": "pii_only",
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Global instance
_pii_db: PIIDatabase | None = None


def get_pii_db() -> PIIDatabase:
    """Get or create PII database instance."""
    global _pii_db
    if _pii_db is None:
        db_path = os.getenv("PII_DB_PATH", "data/pii/pii_mapping.db")
        _pii_db = PIIDatabase(db_path)
    return _pii_db
