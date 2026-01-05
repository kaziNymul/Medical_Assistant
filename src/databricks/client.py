"""
Databricks Workspace Client.

Provides connection management and workspace operations.
"""

import os
import logging
from typing import Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import databricks SDK
try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service import sql
    DATABRICKS_AVAILABLE = True
except ImportError:
    DATABRICKS_AVAILABLE = False
    logger.warning("databricks-sdk not installed. Install with: pip install databricks-sdk")


class DatabricksClient:
    """
    Databricks workspace client for data operations.
    
    Supports:
    - Workspace operations
    - Cluster management
    - SQL warehouse queries
    - Delta table operations
    """
    
    def __init__(
        self,
        host: str | None = None,
        token: str | None = None,
    ):
        """
        Initialize Databricks client.
        
        Args:
            host: Databricks workspace URL
            token: Databricks access token
        """
        self.host = host or os.getenv("DATABRICKS_HOST")
        self.token = token or os.getenv("DATABRICKS_TOKEN")
        self._client: WorkspaceClient | None = None
        self._connected = False
    
    @property
    def client(self) -> "WorkspaceClient | None":
        """Get or create Databricks client."""
        if not DATABRICKS_AVAILABLE:
            logger.warning("Databricks SDK not available")
            return None
        
        if self._client is None and self.host and self.token:
            try:
                self._client = WorkspaceClient(
                    host=self.host,
                    token=self.token,
                )
                # Test connection
                user = self._client.current_user.me()
                self._connected = True
                logger.info(f"Connected to Databricks as {user.user_name}")
            except Exception as e:
                logger.error(f"Failed to connect to Databricks: {e}")
                self._client = None
        
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Databricks."""
        if self._client is None:
            _ = self.client  # Try to connect
        return self._connected
    
    def get_current_user(self) -> dict[str, Any]:
        """Get current user info."""
        if not self.is_connected:
            return {"error": "Not connected"}
        
        user = self.client.current_user.me()
        return {
            "user_name": user.user_name,
            "display_name": user.display_name,
            "active": user.active,
        }
    
    def list_clusters(self) -> list[dict[str, Any]]:
        """List available clusters."""
        if not self.is_connected:
            return []
        
        try:
            clusters = self.client.clusters.list()
            return [
                {
                    "cluster_id": c.cluster_id,
                    "cluster_name": c.cluster_name,
                    "state": str(c.state) if c.state else "UNKNOWN",
                    "spark_version": c.spark_version,
                }
                for c in clusters
            ]
        except Exception as e:
            logger.error(f"Failed to list clusters: {e}")
            return []
    
    def list_warehouses(self) -> list[dict[str, Any]]:
        """List SQL warehouses."""
        if not self.is_connected:
            return []
        
        try:
            warehouses = self.client.warehouses.list()
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "state": str(w.state) if w.state else "UNKNOWN",
                    "size": w.cluster_size,
                }
                for w in warehouses
            ]
        except Exception as e:
            logger.error(f"Failed to list warehouses: {e}")
            return []
    
    def execute_sql(self, query: str, warehouse_id: str | None = None) -> list[dict]:
        """
        Execute SQL query using SQL warehouse.
        
        Args:
            query: SQL query to execute
            warehouse_id: SQL warehouse ID (uses first available if not specified)
            
        Returns:
            List of result rows as dictionaries
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Databricks")
        
        # Get warehouse ID if not specified
        if warehouse_id is None:
            warehouses = self.list_warehouses()
            if not warehouses:
                raise RuntimeError("No SQL warehouses available")
            warehouse_id = warehouses[0]["id"]
        
        try:
            # Execute statement
            response = self.client.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=query,
                wait_timeout="30s",
            )
            
            if response.status and response.status.state:
                if str(response.status.state) == "SUCCEEDED":
                    # Parse results
                    if response.result and response.result.data_array:
                        columns = [c.name for c in response.manifest.schema.columns]
                        return [
                            dict(zip(columns, row))
                            for row in response.result.data_array
                        ]
            
            return []
            
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise


# Global client instance
_databricks_client: DatabricksClient | None = None


def get_databricks_client(force_reconnect: bool = False) -> DatabricksClient:
    """Get Databricks client instance."""
    global _databricks_client
    
    if _databricks_client is not None and not force_reconnect:
        return _databricks_client
    
    host = None
    token = None
    
    # Try to get credentials from Vault first
    try:
        import hvac
        vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN")
        
        if vault_token:
            client = hvac.Client(url=vault_addr, token=vault_token)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(
                    path="medical-assistant",
                    mount_point="secret",
                    raise_on_deleted_version=False,
                )
                secrets = response.get("data", {}).get("data", {})
                host = secrets.get("DATABRICKS_HOST")
                token = secrets.get("DATABRICKS_TOKEN")
                logger.info("Loaded Databricks credentials from Vault")
    except Exception as e:
        logger.warning(f"Could not get Databricks credentials from Vault: {e}")
    
    # Fall back to environment variables
    if not host:
        host = os.getenv("DATABRICKS_HOST")
        token = os.getenv("DATABRICKS_TOKEN")
    
    _databricks_client = DatabricksClient(host=host, token=token)
    return _databricks_client