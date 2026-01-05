"""
Databricks Integration for Phase 3.

This module provides:
- Delta Lake data pipeline (Bronze → Silver → Gold)
- AI query logging and metrics
- Evaluation dashboards
"""

from .client import DatabricksClient
from .tables import TableManager
from .logging import AILogger

__all__ = ["DatabricksClient", "TableManager", "AILogger"]
