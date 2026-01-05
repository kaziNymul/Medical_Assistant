"""
AI Query Logging for Databricks.

Logs all AI queries, responses, and metrics to Databricks for:
- Monitoring and debugging
- Cost tracking
- Quality evaluation
- Audit trail
"""

import uuid
import logging
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class QueryLog:
    """AI query log entry."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_query: str = ""
    context_documents: list[str] = field(default_factory=list)
    llm_response: str = ""
    response_confidence: float = 0.0
    model_id: str = ""
    latency_ms: float = 0.0
    token_count_input: int = 0
    token_count_output: int = 0
    cost_estimate: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_feedback: str | None = None
    feedback_timestamp: str | None = None


@dataclass
class EvaluationMetric:
    """AI evaluation metric entry."""
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str = ""
    metric_type: str = ""  # accuracy, relevance, latency, cost
    metric_name: str = ""
    metric_value: float = 0.0
    ground_truth: str = ""
    prediction: str = ""
    evaluation_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    evaluator: str = "auto"


class AILogger:
    """
    Logs AI operations to Databricks.
    
    Features:
    - Query/response logging
    - Latency tracking
    - Cost estimation
    - Evaluation metrics
    - User feedback capture
    """
    
    # Cost per 1M tokens (as of Jan 2026)
    COST_PER_TOKEN = {
        "anthropic.claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-haiku": {"input": 0.25, "output": 1.25},
        "amazon.titan-embed-text-v2": {"input": 0.02, "output": 0.0},
    }
    
    def __init__(
        self,
        client: "DatabricksClient | None" = None,
        catalog: str = "healthcare_ai",
        schema: str = "clinical_docs",
        local_fallback: bool = True,
    ):
        """
        Initialize AI logger.
        
        Args:
            client: Databricks client
            catalog: Unity Catalog name
            schema: Schema name
            local_fallback: If True, log locally when Databricks unavailable
        """
        self.client = client
        self.catalog = catalog
        self.schema = schema
        self.local_fallback = local_fallback
        self._local_logs: list[QueryLog] = []
        self._local_metrics: list[EvaluationMetric] = []
    
    def log_query(
        self,
        query: str,
        response: str,
        context_docs: list[str] | None = None,
        model_id: str = "anthropic.claude-3-haiku",
        latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        session_id: str = "",
        confidence: float = 0.0,
    ) -> str:
        """
        Log an AI query and response.
        
        Returns:
            Query ID for reference
        """
        # Estimate cost
        cost = self._estimate_cost(model_id, input_tokens, output_tokens)
        
        log_entry = QueryLog(
            session_id=session_id,
            user_query=query,
            context_documents=context_docs or [],
            llm_response=response,
            response_confidence=confidence,
            model_id=model_id,
            latency_ms=latency_ms,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_estimate=cost,
        )
        
        # Try to log to Databricks
        if self.client and self.client.is_connected:
            try:
                self._log_to_databricks(log_entry)
            except Exception as e:
                logger.warning(f"Databricks logging failed: {e}")
                if self.local_fallback:
                    self._local_logs.append(log_entry)
        elif self.local_fallback:
            self._local_logs.append(log_entry)
        
        logger.info(f"Logged query {log_entry.query_id} (${cost:.4f})")
        return log_entry.query_id
    
    def log_feedback(
        self,
        query_id: str,
        feedback: str,  # "positive", "negative", "neutral"
    ) -> bool:
        """Log user feedback for a query."""
        # Find in local logs
        for log in self._local_logs:
            if log.query_id == query_id:
                log.user_feedback = feedback
                log.feedback_timestamp = datetime.utcnow().isoformat()
                return True
        
        # Update in Databricks
        if self.client and self.client.is_connected:
            try:
                sql = f"""
                    UPDATE {self.catalog}.{self.schema}.ai_query_logs
                    SET user_feedback = '{feedback}',
                        feedback_timestamp = current_timestamp()
                    WHERE query_id = '{query_id}'
                """
                self.client.execute_sql(sql)
                return True
            except Exception as e:
                logger.error(f"Failed to log feedback: {e}")
        
        return False
    
    def log_metric(
        self,
        query_id: str,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        ground_truth: str = "",
        prediction: str = "",
    ) -> str:
        """Log an evaluation metric."""
        metric = EvaluationMetric(
            query_id=query_id,
            metric_type=metric_type,
            metric_name=metric_name,
            metric_value=metric_value,
            ground_truth=ground_truth,
            prediction=prediction,
        )
        
        if self.client and self.client.is_connected:
            try:
                self._log_metric_to_databricks(metric)
            except Exception as e:
                logger.warning(f"Databricks metric logging failed: {e}")
                self._local_metrics.append(metric)
        else:
            self._local_metrics.append(metric)
        
        return metric.evaluation_id
    
    def _estimate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD."""
        # Find matching model
        for model_prefix, costs in self.COST_PER_TOKEN.items():
            if model_prefix in model_id:
                input_cost = (input_tokens / 1_000_000) * costs["input"]
                output_cost = (output_tokens / 1_000_000) * costs["output"]
                return input_cost + output_cost
        
        return 0.0
    
    def _log_to_databricks(self, log: QueryLog) -> None:
        """Write log entry to Databricks."""
        docs_str = str(log.context_documents).replace("'", "''")
        query_escaped = log.user_query.replace("'", "''")
        response_escaped = log.llm_response.replace("'", "''")
        
        sql = f"""
            INSERT INTO {self.catalog}.{self.schema}.ai_query_logs
            VALUES (
                '{log.query_id}',
                '{log.session_id}',
                '{query_escaped}',
                array(),
                '{response_escaped}',
                {log.response_confidence},
                '{log.model_id}',
                {log.latency_ms},
                {log.token_count_input},
                {log.token_count_output},
                {log.cost_estimate},
                '{log.timestamp}',
                NULL,
                NULL
            )
        """
        self.client.execute_sql(sql)
    
    def _log_metric_to_databricks(self, metric: EvaluationMetric) -> None:
        """Write metric to Databricks."""
        sql = f"""
            INSERT INTO {self.catalog}.{self.schema}.ai_evaluation_metrics
            VALUES (
                '{metric.evaluation_id}',
                '{metric.query_id}',
                '{metric.metric_type}',
                '{metric.metric_name}',
                {metric.metric_value},
                '{metric.ground_truth}',
                '{metric.prediction}',
                '{metric.evaluation_timestamp}',
                '{metric.evaluator}'
            )
        """
        self.client.execute_sql(sql)
    
    def get_local_logs(self) -> list[dict]:
        """Get locally stored logs."""
        return [asdict(log) for log in self._local_logs]
    
    def get_local_metrics(self) -> list[dict]:
        """Get locally stored metrics."""
        return [asdict(m) for m in self._local_metrics]
    
    def get_stats(self) -> dict[str, Any]:
        """Get logging statistics."""
        total_cost = sum(log.cost_estimate for log in self._local_logs)
        total_queries = len(self._local_logs)
        avg_latency = (
            sum(log.latency_ms for log in self._local_logs) / total_queries
            if total_queries > 0 else 0
        )
        
        return {
            "total_queries": total_queries,
            "total_cost_usd": round(total_cost, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "local_logs_count": len(self._local_logs),
            "local_metrics_count": len(self._local_metrics),
            "databricks_connected": self.client.is_connected if self.client else False,
        }


# Global logger instance
_ai_logger: AILogger | None = None


def get_ai_logger() -> AILogger:
    """Get or create AI logger instance."""
    global _ai_logger
    
    if _ai_logger is None:
        try:
            from src.databricks.client import get_databricks_client
            client = get_databricks_client()
            _ai_logger = AILogger(client=client)
        except Exception:
            _ai_logger = AILogger(client=None)
    
    return _ai_logger
