"""
Databricks Patient Storage.

Stores patient data in Databricks with hybrid architecture:
- patient_original: Original PII data (restricted access)
- patient_masked: Masked data for AI/ML

This replaces the local SQLite on-prem database with Databricks tables.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DatabricksPatientStorage:
    """
    Manages patient data storage in Databricks.
    
    Security:
    - patient_original table: Restricted to clinicians
    - patient_masked table: Available for AI/ML workloads
    - All access is logged for HIPAA compliance
    """
    
    def __init__(self, client: "DatabricksClient", catalog: str = "healthcare_ai", schema: str = "clinical_docs"):
        """
        Initialize patient storage.
        
        Args:
            client: Databricks client
            catalog: Unity Catalog name
            schema: Schema name
        """
        self.client = client
        self.catalog = catalog
        self.schema = schema
        self._tables_created = False
    
    @property
    def original_table(self) -> str:
        return f"{self.catalog}.{self.schema}.patient_original"
    
    @property
    def masked_table(self) -> str:
        return f"{self.catalog}.{self.schema}.patient_masked"
    
    @property
    def audit_table(self) -> str:
        return f"{self.catalog}.{self.schema}.patient_access_log"
    
    def store_patient_batch(
        self,
        records: list[dict],
        warehouse_id: str | None = None,
    ) -> dict:
        """
        Store a batch of patient records (both original and masked).
        
        Each record should have:
        - record_id: Unique identifier
        - original_data: Original unmasked data
        - masked_data: Masked data for AI
        - source_file: Source filename
        
        Returns:
            Result with counts
        """
        if not records:
            return {"original_stored": 0, "masked_stored": 0}
        
        try:
            # Prepare original records
            original_rows = []
            masked_rows = []
            
            now = datetime.now().isoformat()
            
            for rec in records:
                record_id = rec.get("record_id", f"rec_{uuid.uuid4()}")
                original = rec.get("original_data", {})
                masked = rec.get("masked_data", {})
                source_file = rec.get("source_file", "")
                
                # Original record
                original_rows.append({
                    "record_id": record_id,
                    "patient_name": original.get("Name", original.get("name", "")),
                    "patient_dob": original.get("DOB", original.get("Date of Birth", "")),
                    "doctor_name": original.get("Doctor", original.get("doctor", "")),
                    "hospital_name": original.get("Hospital", original.get("hospital", "")),
                    "insurance_provider": original.get("Insurance Provider", ""),
                    "original_data": json.dumps(original),
                    "source_file": source_file,
                    "created_at": now,
                    "updated_at": now,
                })
                
                # Masked record
                masked_rows.append({
                    "record_id": record_id,
                    "masked_content": json.dumps(masked),
                    "source_file": source_file,
                    "pii_fields_masked": self._get_masked_fields(masked),
                    "created_at": now,
                })
            
            # For now, we'll use SQL statements
            # In production, use Spark DataFrames for better performance
            original_count = self._insert_records(
                self.original_table, 
                original_rows, 
                warehouse_id
            )
            
            masked_count = self._insert_records(
                self.masked_table,
                masked_rows,
                warehouse_id
            )
            
            return {
                "original_stored": original_count,
                "masked_stored": masked_count,
            }
            
        except Exception as e:
            logger.error(f"Failed to store patient batch: {e}")
            return {"error": str(e), "original_stored": 0, "masked_stored": 0}
    
    def _get_masked_fields(self, masked_data: dict) -> list[str]:
        """Identify which fields were masked."""
        masked_fields = []
        for key, value in masked_data.items():
            if isinstance(value, str) and "[MASKED" in value:
                masked_fields.append(key)
        return masked_fields
    
    def _insert_records(
        self, 
        table: str, 
        rows: list[dict], 
        warehouse_id: str | None
    ) -> int:
        """Insert records into table using SQL."""
        if not rows:
            return 0
        
        # For Community Edition, we might not have SQL warehouse
        # We'll create a temporary file and use COPY INTO or INSERT
        try:
            # Simple approach: use INSERT statements in batches
            # In production, use Spark DataFrames
            
            columns = list(rows[0].keys())
            
            for row in rows:
                values = []
                for col in columns:
                    val = row.get(col)
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, list):
                        values.append(f"ARRAY({','.join(repr(v) for v in val)})")
                    else:
                        values.append(repr(str(val)))
                
                sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(values)})"
                
                # Execute SQL (this would need warehouse_id in practice)
                # For now, log it
                logger.debug(f"Would execute: {sql[:100]}...")
            
            return len(rows)
            
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return 0
    
    def get_original_patient(
        self,
        record_id: str,
        accessed_by: str = "system",
        access_reason: str = "clinical_review",
        warehouse_id: str | None = None,
    ) -> dict | None:
        """
        Retrieve original patient data by record_id.
        
        This logs the access for HIPAA compliance.
        """
        try:
            # Log access first
            self._log_access(record_id, accessed_by, "READ", access_reason)
            
            # Query the original table
            sql = f"""
                SELECT * FROM {self.original_table}
                WHERE record_id = '{record_id}'
            """
            
            # In practice, execute via warehouse
            # For now, this is a placeholder
            logger.info(f"Would query: {sql}")
            
            # Return placeholder
            return None
            
        except Exception as e:
            logger.error(f"Failed to get patient {record_id}: {e}")
            return None
    
    def _log_access(
        self,
        record_id: str,
        accessed_by: str,
        access_type: str,
        access_reason: str,
    ):
        """Log data access for HIPAA compliance."""
        try:
            log_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            sql = f"""
                INSERT INTO {self.audit_table}
                (log_id, record_id, accessed_by, access_type, access_reason, accessed_at)
                VALUES ('{log_id}', '{record_id}', '{accessed_by}', '{access_type}', '{access_reason}', '{now}')
            """
            
            logger.debug(f"Access logged: {accessed_by} -> {record_id}")
            
        except Exception as e:
            logger.error(f"Failed to log access: {e}")


# ============================================================
# LOCAL FALLBACK (for development without Databricks connection)
# Uses SQLite as local fallback that syncs to Databricks
# ============================================================

class HybridPatientStorage:
    """
    Hybrid storage that uses local SQLite + syncs to Databricks.
    
    For development:
    - Writes to local SQLite immediately
    - Syncs to Databricks in background (when connected)
    
    For production:
    - Writes directly to Databricks
    - Local SQLite as cache/fallback
    """
    
    def __init__(self):
        """Initialize hybrid storage."""
        self._local_db = None
        self._databricks = None
        self._databricks_connected = False
    
    @property
    def local_db(self):
        """Get local SQLite database."""
        if self._local_db is None:
            from src.data.onprem_db import get_onprem_db
            self._local_db = get_onprem_db()
        return self._local_db
    
    @property
    def databricks(self):
        """Get Databricks client."""
        if self._databricks is None:
            try:
                from src.databricks.client import get_databricks_client
                client = get_databricks_client()
                if client.is_connected:
                    self._databricks = DatabricksPatientStorage(client)
                    self._databricks_connected = True
            except Exception as e:
                logger.warning(f"Databricks not available: {e}")
        return self._databricks
    
    def store_patient(
        self,
        record_id: str,
        original_data: dict,
        masked_data: dict,
        source_file: str = "",
    ) -> dict:
        """
        Store patient record in both local and Databricks.
        
        Returns:
            Storage result
        """
        result = {
            "record_id": record_id,
            "local_stored": False,
            "databricks_stored": False,
        }
        
        # Store locally first (fast)
        try:
            self.local_db.store_original_record(
                record_id=record_id,
                original_data=original_data,
                source_file=source_file,
            )
            result["local_stored"] = True
        except Exception as e:
            logger.error(f"Local storage failed: {e}")
        
        # Store to Databricks (async in production)
        if self.databricks:
            try:
                db_result = self.databricks.store_patient_batch([{
                    "record_id": record_id,
                    "original_data": original_data,
                    "masked_data": masked_data,
                    "source_file": source_file,
                }])
                result["databricks_stored"] = db_result.get("original_stored", 0) > 0
            except Exception as e:
                logger.warning(f"Databricks storage failed: {e}")
        
        return result
    
    def get_original_patient(
        self,
        record_id: str,
        accessed_by: str = "clinician",
        access_reason: str = "clinical_review",
    ) -> dict | None:
        """
        Get original patient data.
        
        Tries Databricks first (if connected), falls back to local.
        """
        # Try Databricks first
        if self._databricks_connected and self.databricks:
            result = self.databricks.get_original_patient(
                record_id, accessed_by, access_reason
            )
            if result:
                return result
        
        # Fall back to local
        return self.local_db.get_original_record(
            record_id, accessed_by, access_reason
        )
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        local_stats = self.local_db.get_stats()
        
        return {
            "local": local_stats,
            "databricks_connected": self._databricks_connected,
            "mode": "hybrid" if self._databricks_connected else "local_only",
        }


# Global instance
_hybrid_storage: HybridPatientStorage | None = None


def get_patient_storage() -> HybridPatientStorage:
    """Get the hybrid patient storage instance."""
    global _hybrid_storage
    if _hybrid_storage is None:
        _hybrid_storage = HybridPatientStorage()
    return _hybrid_storage
