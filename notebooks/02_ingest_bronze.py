# Databricks notebook source
# MAGIC %md
# MAGIC # Medical Assistant - Data Ingestion (Bronze Layer)
# MAGIC 
# MAGIC This notebook ingests raw medical data into the Bronze layer.
# MAGIC 
# MAGIC **Data Sources:**
# MAGIC - CSV files from Kaggle datasets
# MAGIC - JSON processed files
# MAGIC - Clinical notes

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *
import uuid
from datetime import datetime

# Use the medical_assistant database
spark.sql("USE medical_assistant")

print("✅ Using database: medical_assistant")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Define Schema for Bronze Layer

# COMMAND ----------

bronze_schema = StructType([
    StructField("record_id", StringType(), False),
    StructField("source_file", StringType(), True),
    StructField("raw_content", StringType(), True),
    StructField("content_type", StringType(), True),
    StructField("ingestion_timestamp", TimestampType(), True),
    StructField("file_metadata", MapType(StringType(), StringType()), True),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Sample Data Ingestion
# MAGIC 
# MAGIC This shows how to ingest data. In production, you would:
# MAGIC 1. Upload files to Databricks FileStore or cloud storage
# MAGIC 2. Read from the storage location
# MAGIC 3. Transform and load into Bronze table

# COMMAND ----------

# Sample medical records for demonstration
sample_records = [
    {
        "record_id": str(uuid.uuid4()),
        "source_file": "kaggle_medical_records.csv",
        "raw_content": "Patient presented with fever and cough. Temperature 101.5F. Diagnosis: Upper respiratory infection. Prescribed amoxicillin 500mg TID for 7 days.",
        "content_type": "clinical_note",
        "ingestion_timestamp": datetime.now(),
        "file_metadata": {"dataset": "kaggle", "version": "1.0"}
    },
    {
        "record_id": str(uuid.uuid4()),
        "source_file": "kaggle_medical_records.csv", 
        "raw_content": "Follow-up visit for hypertension. BP 145/92. Adjusted lisinopril to 20mg daily. Patient advised on low-sodium diet.",
        "content_type": "clinical_note",
        "ingestion_timestamp": datetime.now(),
        "file_metadata": {"dataset": "kaggle", "version": "1.0"}
    },
    {
        "record_id": str(uuid.uuid4()),
        "source_file": "lab_results.csv",
        "raw_content": "Lab Results: WBC 11.2, RBC 4.8, Hemoglobin 14.2, Glucose 110, Creatinine 1.1",
        "content_type": "lab_result",
        "ingestion_timestamp": datetime.now(),
        "file_metadata": {"dataset": "lab_data", "version": "1.0"}
    },
]

# Create DataFrame
df_sample = spark.createDataFrame(sample_records)

# Show sample data
display(df_sample)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Write to Bronze Table

# COMMAND ----------

# Append to Bronze table
df_sample.write.format("delta").mode("append").saveAsTable("bronze_medical_records")

print(f"✅ Ingested {df_sample.count()} records to bronze_medical_records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Verify Ingestion

# COMMAND ----------

# Count records
count = spark.sql("SELECT COUNT(*) as count FROM bronze_medical_records").collect()[0]["count"]
print(f"\n📊 Total records in Bronze layer: {count}")

# Show sample
display(spark.sql("SELECT * FROM bronze_medical_records LIMIT 5"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Upload Your Own Data
# MAGIC 
# MAGIC To ingest your Kaggle data:
# MAGIC 
# MAGIC ```python
# MAGIC # 1. Upload files to Databricks FileStore
# MAGIC # Use the UI: Data > Create Table > Upload File
# MAGIC 
# MAGIC # 2. Read the uploaded CSV
# MAGIC df = spark.read.csv("/FileStore/tables/your_medical_data.csv", header=True)
# MAGIC 
# MAGIC # 3. Transform to Bronze schema
# MAGIC df_bronze = df.select(
# MAGIC     lit(str(uuid.uuid4())).alias("record_id"),
# MAGIC     lit("your_medical_data.csv").alias("source_file"),
# MAGIC     concat_ws(" | ", *df.columns).alias("raw_content"),
# MAGIC     lit("csv_record").alias("content_type"),
# MAGIC     current_timestamp().alias("ingestion_timestamp"),
# MAGIC     lit(None).cast(MapType(StringType(), StringType())).alias("file_metadata")
# MAGIC )
# MAGIC 
# MAGIC # 4. Write to Bronze
# MAGIC df_bronze.write.format("delta").mode("append").saveAsTable("bronze_medical_records")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Bronze Layer Ready!
# MAGIC 
# MAGIC Next: Run the processing notebook to create Silver layer
