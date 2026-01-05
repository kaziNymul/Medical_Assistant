"""
Delta Lake Table Management.

Creates and manages Bronze → Silver → Gold data pipeline tables.
Also manages AI logging and evaluation tables.

HYBRID ARCHITECTURE:
- patient_original: ORIGINAL data (restricted access - clinicians only)
- patient_masked: MASKED data (AI/ML access)
- Both linked by record_id
"""

import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TableManager:
    """
    Manages Delta Lake tables in Databricks.
    
    Tables:
    - patient_original: Original PII data (RESTRICTED)
    - patient_masked: Masked data for AI
    - Bronze: Raw medical data
    - Silver: Cleaned and masked data
    - Gold: ML-ready processed data
    - AI Logs: Query/response logs
    - Metrics: Evaluation metrics
    """
    
    # Table schemas
    SCHEMAS = {
        # ===== ORIGINAL PATIENT DATA (RESTRICTED ACCESS) =====
        "patient_original": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.patient_original (
                record_id STRING PRIMARY KEY,
                patient_name STRING,
                patient_dob STRING,
                patient_ssn STRING,
                patient_phone STRING,
                patient_email STRING,
                patient_address STRING,
                doctor_name STRING,
                hospital_name STRING,
                insurance_provider STRING,
                medical_record_number STRING,
                original_data STRING,
                source_file STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            USING DELTA
            COMMENT 'RESTRICTED: Original patient data with PII. Clinician access only.'
            TBLPROPERTIES (
                'delta.enableChangeDataFeed' = 'true',
                'security.classification' = 'PHI',
                'access.restricted' = 'true'
            )
        """,
        
        # ===== ACCESS AUDIT LOG (HIPAA COMPLIANCE) =====
        "patient_access_log": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.patient_access_log (
                log_id STRING,
                record_id STRING,
                accessed_by STRING,
                access_type STRING,
                access_reason STRING,
                ip_address STRING,
                accessed_at TIMESTAMP
            )
            USING DELTA
            COMMENT 'HIPAA audit log for patient data access'
        """,
        
        # ===== MASKED DATA FOR AI =====
        "patient_masked": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.patient_masked (
                record_id STRING PRIMARY KEY,
                masked_content STRING,
                source_file STRING,
                pii_fields_masked ARRAY<STRING>,
                created_at TIMESTAMP
            )
            USING DELTA
            COMMENT 'Masked patient data safe for AI/ML processing'
        """,
        
        "bronze_medical_records": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.bronze_medical_records (
                record_id STRING,
                source_file STRING,
                raw_content STRING,
                content_type STRING,
                ingestion_timestamp TIMESTAMP,
                file_metadata MAP<STRING, STRING>
            )
            USING DELTA
            COMMENT 'Raw medical records ingested from various sources'
        """,
        
        "silver_medical_records": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.silver_medical_records (
                record_id STRING,
                source_record_id STRING,
                patient_id_masked STRING,
                content_cleaned STRING,
                content_masked STRING,
                entities_extracted MAP<STRING, STRING>,
                pii_detected ARRAY<STRING>,
                processing_timestamp TIMESTAMP,
                quality_score DOUBLE
            )
            USING DELTA
            COMMENT 'Cleaned and PII-masked medical records'
        """,
        
        "gold_medical_records": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.gold_medical_records (
                record_id STRING,
                source_record_id STRING,
                diagnosis_codes ARRAY<STRING>,
                medications ARRAY<STRING>,
                procedures ARRAY<STRING>,
                patient_summary STRING,
                embeddings ARRAY<DOUBLE>,
                embedding_model STRING,
                processing_timestamp TIMESTAMP,
                is_vectorized BOOLEAN
            )
            USING DELTA
            COMMENT 'ML-ready processed medical records with embeddings'
        """,
        
        "ai_query_logs": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.ai_query_logs (
                query_id STRING,
                session_id STRING,
                user_query STRING,
                context_documents ARRAY<STRING>,
                llm_response STRING,
                response_confidence DOUBLE,
                model_id STRING,
                latency_ms DOUBLE,
                token_count_input INT,
                token_count_output INT,
                cost_estimate DOUBLE,
                timestamp TIMESTAMP,
                user_feedback STRING,
                feedback_timestamp TIMESTAMP
            )
            USING DELTA
            COMMENT 'AI query and response logs for monitoring'
        """,
        
        "ai_evaluation_metrics": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.ai_evaluation_metrics (
                evaluation_id STRING,
                query_id STRING,
                metric_type STRING,
                metric_name STRING,
                metric_value DOUBLE,
                ground_truth STRING,
                prediction STRING,
                evaluation_timestamp TIMESTAMP,
                evaluator STRING
            )
            USING DELTA
            COMMENT 'AI evaluation metrics for quality monitoring'
        """,
        
        "pii_audit_log": """
            CREATE TABLE IF NOT EXISTS {catalog}.{schema}.pii_audit_log (
                audit_id STRING,
                record_id STRING,
                pii_type STRING,
                pii_location STRING,
                masking_method STRING,
                original_hash STRING,
                masked_value STRING,
                audit_timestamp TIMESTAMP,
                auditor STRING
            )
            USING DELTA
            COMMENT 'Audit log for PII detection and masking'
        """
    }
    
    def __init__(
        self,
        client: "DatabricksClient",
        catalog: str = "healthcare_ai",
        schema: str = "clinical_docs",
    ):
        """
        Initialize table manager.
        
        Args:
            client: Databricks client
            catalog: Unity Catalog name
            schema: Schema name within catalog
        """
        self.client = client
        self.catalog = catalog
        self.schema = schema
    
    def create_catalog_and_schema(self, warehouse_id: str | None = None) -> bool:
        """Create catalog and schema if they don't exist."""
        try:
            # Note: Community Edition doesn't support Unity Catalog
            # We'll use default catalog/schema
            logger.info(f"Using catalog: {self.catalog}, schema: {self.schema}")
            return True
        except Exception as e:
            logger.warning(f"Could not create catalog/schema: {e}")
            return False
    
    def create_all_tables(self, warehouse_id: str | None = None) -> dict[str, bool]:
        """
        Create all required tables.
        
        Returns:
            Dictionary of table name -> creation success
        """
        results = {}
        
        for table_name, schema_sql in self.SCHEMAS.items():
            try:
                sql = schema_sql.format(
                    catalog=self.catalog,
                    schema=self.schema,
                )
                self.client.execute_sql(sql, warehouse_id)
                results[table_name] = True
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                results[table_name] = False
                logger.error(f"Failed to create {table_name}: {e}")
        
        return results
    
    def get_table_stats(self, table_name: str, warehouse_id: str | None = None) -> dict:
        """Get statistics for a table."""
        try:
            full_table = f"{self.catalog}.{self.schema}.{table_name}"
            result = self.client.execute_sql(
                f"SELECT COUNT(*) as row_count FROM {full_table}",
                warehouse_id
            )
            return {
                "table": table_name,
                "row_count": result[0]["row_count"] if result else 0,
            }
        except Exception as e:
            return {"table": table_name, "error": str(e)}
    
    def insert_bronze_record(
        self,
        record_id: str,
        source_file: str,
        raw_content: str,
        content_type: str,
        metadata: dict | None = None,
        warehouse_id: str | None = None,
    ) -> bool:
        """Insert a record into bronze layer."""
        try:
            timestamp = datetime.utcnow().isoformat()
            metadata_str = str(metadata or {})
            
            sql = f"""
                INSERT INTO {self.catalog}.{self.schema}.bronze_medical_records
                VALUES (
                    '{record_id}',
                    '{source_file}',
                    '{raw_content.replace("'", "''")}',
                    '{content_type}',
                    '{timestamp}',
                    map()
                )
            """
            self.client.execute_sql(sql, warehouse_id)
            return True
        except Exception as e:
            logger.error(f"Failed to insert bronze record: {e}")
            return False


# Simplified version for Community Edition (no SQL warehouse)
class LocalTableManager:
    """
    Local simulation of Databricks tables using Delta Lake.
    
    For use with Community Edition which may not have SQL warehouses.
    Uses local Delta Lake files for storage.
    """
    
    def __init__(self, data_path: str = "./data/delta"):
        """Initialize local table manager."""
        self.data_path = data_path
        self._tables = {}
    
    def create_all_tables(self) -> dict[str, bool]:
        """Create local Delta tables."""
        import os
        
        tables = [
            "bronze_medical_records",
            "silver_medical_records", 
            "gold_medical_records",
            "ai_query_logs",
            "ai_evaluation_metrics",
            "pii_audit_log",
        ]
        
        results = {}
        for table in tables:
            table_path = os.path.join(self.data_path, table)
            os.makedirs(table_path, exist_ok=True)
            results[table] = True
        
        return results
