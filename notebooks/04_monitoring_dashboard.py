# Databricks notebook source
# MAGIC %md
# MAGIC # Medical Assistant - AI Monitoring Dashboard
# MAGIC 
# MAGIC This notebook provides visualizations for:
# MAGIC - Query volume and trends
# MAGIC - Response latency
# MAGIC - Cost tracking
# MAGIC - Model usage
# MAGIC - Quality metrics

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup

# COMMAND ----------

from pyspark.sql.functions import *
from datetime import datetime, timedelta

spark.sql("USE medical_assistant")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Query Volume Over Time

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     DATE(timestamp) as date,
# MAGIC     COUNT(*) as query_count,
# MAGIC     AVG(latency_ms) as avg_latency_ms,
# MAGIC     SUM(cost_estimate) as total_cost
# MAGIC FROM ai_query_logs
# MAGIC GROUP BY DATE(timestamp)
# MAGIC ORDER BY date DESC
# MAGIC LIMIT 30

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Model Usage Distribution

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     model_id,
# MAGIC     COUNT(*) as query_count,
# MAGIC     AVG(latency_ms) as avg_latency,
# MAGIC     SUM(token_count_input) as total_input_tokens,
# MAGIC     SUM(token_count_output) as total_output_tokens,
# MAGIC     SUM(cost_estimate) as total_cost
# MAGIC FROM ai_query_logs
# MAGIC GROUP BY model_id
# MAGIC ORDER BY query_count DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Response Latency Distribution

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     CASE 
# MAGIC         WHEN latency_ms < 500 THEN '0-500ms'
# MAGIC         WHEN latency_ms < 1000 THEN '500-1000ms'
# MAGIC         WHEN latency_ms < 2000 THEN '1-2s'
# MAGIC         WHEN latency_ms < 5000 THEN '2-5s'
# MAGIC         ELSE '5s+'
# MAGIC     END as latency_bucket,
# MAGIC     COUNT(*) as count
# MAGIC FROM ai_query_logs
# MAGIC GROUP BY 1
# MAGIC ORDER BY 
# MAGIC     CASE latency_bucket
# MAGIC         WHEN '0-500ms' THEN 1
# MAGIC         WHEN '500-1000ms' THEN 2
# MAGIC         WHEN '1-2s' THEN 3
# MAGIC         WHEN '2-5s' THEN 4
# MAGIC         ELSE 5
# MAGIC     END

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. User Feedback Analysis

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     COALESCE(user_feedback, 'No Feedback') as feedback,
# MAGIC     COUNT(*) as count,
# MAGIC     ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
# MAGIC FROM ai_query_logs
# MAGIC GROUP BY user_feedback
# MAGIC ORDER BY count DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Cost Analysis

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     DATE(timestamp) as date,
# MAGIC     model_id,
# MAGIC     SUM(cost_estimate) as daily_cost,
# MAGIC     SUM(SUM(cost_estimate)) OVER (ORDER BY DATE(timestamp)) as cumulative_cost
# MAGIC FROM ai_query_logs
# MAGIC GROUP BY DATE(timestamp), model_id
# MAGIC ORDER BY date DESC
# MAGIC LIMIT 30

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Quality Metrics Summary

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     metric_type,
# MAGIC     metric_name,
# MAGIC     COUNT(*) as evaluations,
# MAGIC     ROUND(AVG(metric_value), 4) as avg_value,
# MAGIC     ROUND(MIN(metric_value), 4) as min_value,
# MAGIC     ROUND(MAX(metric_value), 4) as max_value
# MAGIC FROM ai_evaluation_metrics
# MAGIC GROUP BY metric_type, metric_name
# MAGIC ORDER BY metric_type, metric_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Data Pipeline Health

# COMMAND ----------

# Check record counts across layers
pipeline_health = spark.sql("""
    SELECT 'Bronze' as layer, COUNT(*) as records, MAX(ingestion_timestamp) as last_update
    FROM bronze_medical_records
    UNION ALL
    SELECT 'Silver' as layer, COUNT(*) as records, MAX(processing_timestamp) as last_update
    FROM silver_medical_records  
    UNION ALL
    SELECT 'Gold' as layer, COUNT(*) as records, MAX(processing_timestamp) as last_update
    FROM gold_medical_records
""")

display(pipeline_health)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. PII Audit Summary

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC     pii_type,
# MAGIC     masking_method,
# MAGIC     COUNT(*) as occurrences,
# MAGIC     COUNT(DISTINCT record_id) as affected_records
# MAGIC FROM pii_audit_log
# MAGIC GROUP BY pii_type, masking_method
# MAGIC ORDER BY occurrences DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Dashboard Ready!
# MAGIC 
# MAGIC This dashboard shows:
# MAGIC - 📊 Query volumes and trends
# MAGIC - ⏱️ Response latency distribution
# MAGIC - 💰 Cost tracking by model
# MAGIC - 👍 User feedback analysis
# MAGIC - 📈 Quality metrics
# MAGIC - 🏥 Data pipeline health
# MAGIC - 🔒 PII audit trail
# MAGIC 
# MAGIC Schedule this notebook to run daily for automated reporting.
