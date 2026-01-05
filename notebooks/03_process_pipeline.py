# Databricks notebook source
# MAGIC %md
# MAGIC # Medical Assistant - Data Processing (Bronze → Silver → Gold)
# MAGIC 
# MAGIC This notebook processes data through the medallion architecture:
# MAGIC - **Bronze → Silver**: Clean data, mask PII
# MAGIC - **Silver → Gold**: Extract entities, generate embeddings

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *
import uuid
import re
import hashlib
from datetime import datetime

spark.sql("USE medical_assistant")

print("✅ Using database: medical_assistant")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. PII Masking Functions

# COMMAND ----------

# PII patterns
PII_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PHONE": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "DOB": r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    "MRN": r"\bMRN[:\s]?\d{6,10}\b",
    "NAME": r"\b(Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
}

def mask_pii(text):
    """Mask PII in text and return masked text + detected PII types."""
    if not text:
        return text, []
    
    masked = text
    detected = []
    
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, masked, re.IGNORECASE)
        if matches:
            detected.append(pii_type)
            masked = re.sub(pattern, f"[MASKED_{pii_type}]", masked, flags=re.IGNORECASE)
    
    return masked, detected

# Register as UDF
@udf(returnType=StructType([
    StructField("masked_content", StringType()),
    StructField("pii_detected", ArrayType(StringType()))
]))
def mask_pii_udf(text):
    masked, detected = mask_pii(text)
    return {"masked_content": masked, "pii_detected": detected}

print("✅ PII masking functions registered")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Bronze → Silver Transformation

# COMMAND ----------

# Read from Bronze
df_bronze = spark.sql("""
    SELECT * FROM bronze_medical_records
    WHERE record_id NOT IN (SELECT source_record_id FROM silver_medical_records)
""")

print(f"📥 Records to process: {df_bronze.count()}")

# COMMAND ----------

# Apply PII masking
df_masked = df_bronze.withColumn(
    "pii_result", 
    mask_pii_udf(col("raw_content"))
).select(
    lit(str(uuid.uuid4())).alias("record_id"),
    col("record_id").alias("source_record_id"),
    sha2(col("record_id"), 256).alias("patient_id_masked"),
    col("raw_content").alias("content_cleaned"),
    col("pii_result.masked_content").alias("content_masked"),
    lit(None).cast(MapType(StringType(), StringType())).alias("entities_extracted"),
    col("pii_result.pii_detected").alias("pii_detected"),
    current_timestamp().alias("processing_timestamp"),
    lit(1.0).alias("quality_score")
)

display(df_masked.limit(3))

# COMMAND ----------

# Write to Silver
df_masked.write.format("delta").mode("append").saveAsTable("silver_medical_records")

print(f"✅ Wrote {df_masked.count()} records to Silver layer")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Silver → Gold Transformation

# COMMAND ----------

# Read from Silver (unprocessed)
df_silver = spark.sql("""
    SELECT * FROM silver_medical_records
    WHERE record_id NOT IN (SELECT source_record_id FROM gold_medical_records WHERE source_record_id IS NOT NULL)
""")

print(f"📥 Silver records to process: {df_silver.count()}")

# COMMAND ----------

# Simple entity extraction (in production, use NLP/LLM)
@udf(returnType=ArrayType(StringType()))
def extract_medications(text):
    """Extract medication mentions from text."""
    if not text:
        return []
    
    # Common medication patterns
    med_patterns = [
        r"\b[A-Za-z]+(?:cillin|mycin|pril|sartan|olol|pine|statin)\b",
        r"\b\d+\s?mg\b",
    ]
    
    meds = []
    for pattern in med_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        meds.extend(matches)
    
    return list(set(meds))[:10]  # Limit to 10

@udf(returnType=ArrayType(StringType()))
def extract_diagnoses(text):
    """Extract diagnosis mentions from text."""
    if not text:
        return []
    
    # Common diagnosis patterns
    diagnoses = []
    keywords = ["diagnosis", "diagnosed", "condition", "infection", "disease"]
    
    for keyword in keywords:
        if keyword.lower() in text.lower():
            # Get surrounding context
            idx = text.lower().find(keyword.lower())
            context = text[max(0, idx-20):min(len(text), idx+50)]
            diagnoses.append(context.strip())
    
    return diagnoses[:5]

print("✅ Entity extraction functions registered")

# COMMAND ----------

# Transform to Gold
df_gold = df_silver.select(
    lit(str(uuid.uuid4())).alias("record_id"),
    col("record_id").alias("source_record_id"),
    extract_diagnoses(col("content_masked")).alias("diagnosis_codes"),
    extract_medications(col("content_masked")).alias("medications"),
    array().cast(ArrayType(StringType())).alias("procedures"),
    col("content_masked").alias("patient_summary"),
    array().cast(ArrayType(DoubleType())).alias("embeddings"),  # Placeholder
    lit("pending").alias("embedding_model"),
    current_timestamp().alias("processing_timestamp"),
    lit(False).alias("is_vectorized")
)

display(df_gold.limit(3))

# COMMAND ----------

# Write to Gold
df_gold.write.format("delta").mode("append").saveAsTable("gold_medical_records")

print(f"✅ Wrote {df_gold.count()} records to Gold layer")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Pipeline Summary

# COMMAND ----------

# Get counts for each layer
summary = spark.sql("""
    SELECT 
        'Bronze' as layer, COUNT(*) as record_count FROM bronze_medical_records
    UNION ALL
    SELECT 
        'Silver' as layer, COUNT(*) as record_count FROM silver_medical_records
    UNION ALL
    SELECT 
        'Gold' as layer, COUNT(*) as record_count FROM gold_medical_records
""")

display(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Processing Complete!
# MAGIC 
# MAGIC Data has been transformed through all layers:
# MAGIC - **Bronze**: Raw ingested data
# MAGIC - **Silver**: PII-masked and cleaned
# MAGIC - **Gold**: Entity-extracted and ready for ML
# MAGIC 
# MAGIC Next: Generate embeddings using AWS Bedrock
