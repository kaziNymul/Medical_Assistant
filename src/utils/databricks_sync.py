"""
Databricks Sync for Clinical Extractions

Syncs masked and unmasked clinical data to Databricks Unity Catalog.
Creates separate tables for PHI-protected and anonymized data.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

from src.utils.logging import logger


class DatabricksClinicalSync:
    """
    Sync clinical extractions to Databricks.
    
    Tables created:
    - {catalog}.{schema}.clinical_extractions_unmasked (PHI)
    - {catalog}.{schema}.clinical_extractions_masked (safe)
    """
    
    def __init__(
        self,
        host: str = None,
        token: str = None,
        catalog: str = "medical_catalog",
        schema: str = "clinical"
    ):
        self.host = host or os.getenv('DATABRICKS_HOST')
        self.token = token or os.getenv('DATABRICKS_TOKEN')
        self.catalog = catalog
        self.schema = schema
        
        self._connection = None
        
    def _get_connection(self):
        """Get Databricks SQL connection."""
        if self._connection is not None:
            return self._connection
            
        try:
            from databricks import sql
            
            self._connection = sql.connect(
                server_hostname=self.host,
                http_path=os.getenv('DATABRICKS_HTTP_PATH', '/sql/1.0/warehouses/default'),
                access_token=self.token
            )
            
            return self._connection
            
        except ImportError:
            logger.error("databricks-sql-connector not installed. Run: pip install databricks-sql-connector")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Databricks: {e}")
            raise
    
    def _ensure_tables_exist(self, cursor):
        """Create tables if they don't exist."""
        
        # Unmasked table (PHI - restricted access)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.clinical_extractions_unmasked (
                extraction_id STRING,
                patient_id STRING,
                patient_name STRING,
                date_of_birth STRING,
                gender STRING,
                age STRING,
                mrn STRING,
                ssn STRING,
                address STRING,
                phone STRING,
                email STRING,
                insurance_id STRING,
                diagnoses STRING,
                medications STRING,
                allergies STRING,
                procedures STRING,
                lab_results STRING,
                vital_signs STRING,
                visit_date STRING,
                visit_type STRING,
                chief_complaint STRING,
                history_present_illness STRING,
                provider_name STRING,
                provider_npi STRING,
                facility_name STRING,
                assessment STRING,
                plan STRING,
                follow_up STRING,
                source_file STRING,
                extraction_confidence DOUBLE,
                model_used STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            USING DELTA
            COMMENT 'PHI-containing clinical extractions - RESTRICTED ACCESS'
        """)
        
        # Masked table (safe for general access)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.clinical_extractions_masked (
                extraction_id STRING,
                patient_id STRING,
                patient_name_masked STRING,
                date_of_birth_masked STRING,
                gender STRING,
                age STRING,
                mrn_masked STRING,
                diagnoses STRING,
                medications STRING,
                allergies STRING,
                procedures STRING,
                lab_results STRING,
                vital_signs STRING,
                visit_date STRING,
                visit_type STRING,
                chief_complaint STRING,
                assessment STRING,
                plan STRING,
                source_file STRING,
                extraction_confidence DOUBLE,
                model_used STRING,
                created_at TIMESTAMP
            )
            USING DELTA
            COMMENT 'De-identified clinical extractions - SAFE for analytics'
        """)
        
    def sync(
        self,
        unmasked_data: Dict[str, Any],
        masked_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync clinical extraction to both tables.
        
        Args:
            unmasked_data: Full extraction with PHI
            masked_data: Extraction with PII masked
            
        Returns:
            Sync result with status
        """
        import uuid
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Ensure tables exist
            self._ensure_tables_exist(cursor)
            
            extraction_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # Insert unmasked record
            cursor.execute(f"""
                INSERT INTO {self.catalog}.{self.schema}.clinical_extractions_unmasked
                VALUES (
                    '{extraction_id}',
                    '{unmasked_data.get('patient_id', '')}',
                    '{self._escape(unmasked_data.get('patient_name', ''))}',
                    '{unmasked_data.get('date_of_birth', '')}',
                    '{unmasked_data.get('gender', '')}',
                    '{unmasked_data.get('age', '')}',
                    '{unmasked_data.get('mrn', '')}',
                    '{unmasked_data.get('ssn', '')}',
                    '{self._escape(unmasked_data.get('address', ''))}',
                    '{unmasked_data.get('phone', '')}',
                    '{unmasked_data.get('email', '')}',
                    '{unmasked_data.get('insurance_id', '')}',
                    '{self._escape(json.dumps(unmasked_data.get('diagnoses', [])))}',
                    '{self._escape(json.dumps(unmasked_data.get('medications', [])))}',
                    '{self._escape(json.dumps(unmasked_data.get('allergies', [])))}',
                    '{self._escape(json.dumps(unmasked_data.get('procedures', [])))}',
                    '{self._escape(json.dumps(unmasked_data.get('lab_results', [])))}',
                    '{self._escape(json.dumps(unmasked_data.get('vital_signs', {})))}',
                    '{unmasked_data.get('visit_date', '')}',
                    '{unmasked_data.get('visit_type', '')}',
                    '{self._escape(unmasked_data.get('chief_complaint', ''))}',
                    '{self._escape(unmasked_data.get('history_present_illness', ''))}',
                    '{self._escape(unmasked_data.get('provider_name', ''))}',
                    '{unmasked_data.get('provider_npi', '')}',
                    '{self._escape(unmasked_data.get('facility_name', ''))}',
                    '{self._escape(unmasked_data.get('assessment', ''))}',
                    '{self._escape(unmasked_data.get('plan', ''))}',
                    '{self._escape(unmasked_data.get('follow_up', ''))}',
                    '{self._escape(unmasked_data.get('source_file', ''))}',
                    {unmasked_data.get('extraction_confidence', 0.0)},
                    '{unmasked_data.get('model_used', '')}',
                    '{now.isoformat()}',
                    '{now.isoformat()}'
                )
            """)
            
            # Insert masked record
            cursor.execute(f"""
                INSERT INTO {self.catalog}.{self.schema}.clinical_extractions_masked
                VALUES (
                    '{extraction_id}',
                    '{masked_data.get('patient_id', '')}',
                    '{self._escape(masked_data.get('patient_name', ''))}',
                    '{masked_data.get('date_of_birth', '')}',
                    '{masked_data.get('gender', '')}',
                    '{masked_data.get('age', '')}',
                    '{masked_data.get('mrn', '')}',
                    '{self._escape(json.dumps(masked_data.get('diagnoses', [])))}',
                    '{self._escape(json.dumps(masked_data.get('medications', [])))}',
                    '{self._escape(json.dumps(masked_data.get('allergies', [])))}',
                    '{self._escape(json.dumps(masked_data.get('procedures', [])))}',
                    '{self._escape(json.dumps(masked_data.get('lab_results', [])))}',
                    '{self._escape(json.dumps(masked_data.get('vital_signs', {})))}',
                    '{masked_data.get('visit_date', '')}',
                    '{masked_data.get('visit_type', '')}',
                    '{self._escape(masked_data.get('chief_complaint', ''))}',
                    '{self._escape(masked_data.get('assessment', ''))}',
                    '{self._escape(masked_data.get('plan', ''))}',
                    '{self._escape(masked_data.get('source_file', ''))}',
                    {masked_data.get('extraction_confidence', 0.0)},
                    '{masked_data.get('model_used', '')}',
                    '{now.isoformat()}'
                )
            """)
            
            cursor.close()
            
            logger.info(f"Synced extraction {extraction_id} to Databricks")
            
            return {
                'success': True,
                'extraction_id': extraction_id,
                'unmasked_table': f"{self.catalog}.{self.schema}.clinical_extractions_unmasked",
                'masked_table': f"{self.catalog}.{self.schema}.clinical_extractions_masked",
                'synced_at': now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Databricks sync failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _escape(self, value: str) -> str:
        """Escape string for SQL."""
        if value is None:
            return ''
        return str(value).replace("'", "''").replace("\\", "\\\\")
    
    def query_masked(self, patient_id: str = None, limit: int = 100) -> list:
        """Query masked extractions (safe for analytics)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = f"SELECT * FROM {self.catalog}.{self.schema}.clinical_extractions_masked"
            if patient_id:
                query += f" WHERE patient_id = '{patient_id}'"
            query += f" LIMIT {limit}"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            cursor.close()
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []


# Singleton instance
_sync_client = None


def get_databricks_sync() -> DatabricksClinicalSync:
    """Get singleton Databricks sync client."""
    global _sync_client
    if _sync_client is None:
        _sync_client = DatabricksClinicalSync()
    return _sync_client


def sync_clinical_extraction(
    unmasked_data: Dict[str, Any],
    masked_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Convenience function to sync clinical extraction."""
    client = get_databricks_sync()
    return client.sync(unmasked_data, masked_data)
