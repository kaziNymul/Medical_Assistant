# Databricks notebook source
# MAGIC %md
# MAGIC # Medical Assistant - Phase 3 Setup
# MAGIC 
# MAGIC This notebook creates the Delta Lake tables for the Bronze → Silver → Gold data pipeline.
# MAGIC 
# MAGIC **Tables Created:**
# MAGIC - `bronze_medical_records` - Raw ingested data
# MAGIC - `silver_medical_records` - Cleaned and PII-masked data
# MAGIC - `gold_medical_records` - ML-ready with embeddings
# MAGIC - `ai_query_logs` - AI query/response logs
# MAGIC - `ai_evaluation_metrics` - Quality metrics
# MAGIC - `pii_audit_log` - PII masking audit trail

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create Database

# COMMAND ----------

# Create database for medical assistant
spark.sql("CREATE DATABASE IF NOT EXISTS medical_assistant")
spark.sql("USE medical_assistant")

print("✅ Database 'medical_assistant' ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Bronze Layer Table

# COMMAND ----------

# Bronze: Raw medical records
spark.sql("""
    CREATE TABLE IF NOT EXISTS bronze_medical_records (
        record_id STRING,
        source_file STRING,
        raw_content STRING,
        content_type STRING,
        ingestion_timestamp TIMESTAMP,
        file_metadata MAP<STRING, STRING>
    )
    USING DELTA
    COMMENT 'Raw medical records ingested from various sources'
""")

print("✅ Created bronze_medical_records table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Silver Layer Table

# COMMAND ----------

# Silver: Cleaned and masked records
spark.sql("""
    CREATE TABLE IF NOT EXISTS silver_medical_records (
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
""")

print("✅ Created silver_medical_records table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Create Gold Layer Table

# COMMAND ----------

# Gold: ML-ready records with embeddings
spark.sql("""
    CREATE TABLE IF NOT EXISTS gold_medical_records (
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
""")

print("✅ Created gold_medical_records table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Create AI Logging Tables

# COMMAND ----------

# AI Query Logs
spark.sql("""
    CREATE TABLE IF NOT EXISTS ai_query_logs (
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
""")

print("✅ Created ai_query_logs table")

# COMMAND ----------

# AI Evaluation Metrics
spark.sql("""
    CREATE TABLE IF NOT EXISTS ai_evaluation_metrics (
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
""")

print("✅ Created ai_evaluation_metrics table")

# COMMAND ----------

# PII Audit Log
spark.sql("""
    CREATE TABLE IF NOT EXISTS pii_audit_log (
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
""")

print("✅ Created pii_audit_log table")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Verify Tables

# COMMAND ----------

# List all tables
tables = spark.sql("SHOW TABLES IN medical_assistant").collect()
print("\n📋 Tables in medical_assistant database:")
for t in tables:
    print(f"   • {t.tableName}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Setup Complete!
# MAGIC 
# MAGIC Your Delta Lake tables are ready. Next steps:
# MAGIC 1. Run the data ingestion notebook to load medical records
# MAGIC 2. Run the processing pipeline to populate Silver/Gold layers
# MAGIC 3. Connect your FastAPI backend to log queries
