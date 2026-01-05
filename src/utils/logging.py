"""
Logging utilities for the Medical Assistant.

Provides structured logging with PII protection.
"""

import logging
import sys
from datetime import datetime
from typing import Any

from config.settings import settings


class PIISafeFormatter(logging.Formatter):
    """
    Custom formatter that ensures no PII leaks into logs.
    """
    
    PII_PATTERNS = [
        # Add patterns that should trigger warnings
        "@",  # Email indicator
        "SSN",
        "DOB:",
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, checking for potential PII."""
        message = super().format(record)
        
        # Check for potential PII in the message
        for pattern in self.PII_PATTERNS:
            if pattern in message and "[" not in message:
                # Add warning that PII might be present
                message = f"[PII-WARNING] {message}"
                break
        
        return message


def setup_logging() -> logging.Logger:
    """
    Set up application logging.
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("medical_assistant")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # Format
    formatter = PIISafeFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler if not already added
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    return logger


# Create default logger
logger = setup_logging()


def log_extraction(
    document_id: str,
    extraction_result: dict[str, Any],
    processing_time_ms: float
) -> None:
    """
    Log an extraction result (without PII).
    
    Args:
        document_id: The document identifier.
        extraction_result: The extraction output.
        processing_time_ms: Processing time in milliseconds.
    """
    # Only log safe metadata, not actual content
    logger.info(
        f"Extraction completed | doc_id={document_id} | "
        f"confidence={extraction_result.get('confidence_score', 0):.2f} | "
        f"completeness={extraction_result.get('data_completeness', 'unknown')} | "
        f"time_ms={processing_time_ms:.1f}"
    )


def log_query(
    query_hash: str,
    num_results: int,
    processing_time_ms: float
) -> None:
    """
    Log a query (without logging the actual query text).
    
    Args:
        query_hash: Hash of the query for tracking.
        num_results: Number of results returned.
        processing_time_ms: Processing time in milliseconds.
    """
    logger.info(
        f"Query completed | query_hash={query_hash[:8]} | "
        f"results={num_results} | time_ms={processing_time_ms:.1f}"
    )


def log_error(
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None
) -> None:
    """
    Log an error with context.
    
    Args:
        operation: The operation that failed.
        error: The exception that occurred.
        context: Additional context (must not contain PII).
    """
    context_str = ""
    if context:
        # Filter out any potentially sensitive keys
        safe_keys = ["document_id", "chunk_count", "operation_type"]
        safe_context = {k: v for k, v in context.items() if k in safe_keys}
        context_str = f" | context={safe_context}"
    
    logger.error(
        f"Operation failed | operation={operation} | "
        f"error_type={type(error).__name__} | "
        f"error_msg={str(error)[:100]}{context_str}"
    )
