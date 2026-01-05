"""
HashiCorp Vault Integration for Secrets Management.

This module provides secure secrets retrieval from HashiCorp Vault.
Supports both Vault and environment variable fallback.

SETUP:
1. Install Vault: https://developer.hashicorp.com/vault/downloads
2. Start dev server: vault server -dev
3. Set VAULT_ADDR and VAULT_TOKEN environment variables
4. Store secrets: vault kv put secret/medical-assistant AWS_ACCESS_KEY_ID=xxx

USAGE:
    from src.utils.vault import get_secret, get_secrets
    
    # Get single secret
    api_key = get_secret("AWS_ACCESS_KEY_ID")
    
    # Get all secrets for the app
    secrets = get_secrets()
"""

import os
import logging
from typing import Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import hvac (HashiCorp Vault client)
try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False
    logger.warning("hvac not installed. Install with: pip install hvac")


class VaultClient:
    """
    HashiCorp Vault client for secrets management.
    
    Falls back to environment variables if Vault is unavailable.
    """
    
    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        vault_path: str = "secret/data/medical-assistant",
        namespace: str | None = None,
    ):
        """
        Initialize Vault client.
        
        Args:
            vault_addr: Vault server address (default: VAULT_ADDR env var)
            vault_token: Vault token (default: VAULT_TOKEN env var)
            vault_path: Path to secrets in Vault
            namespace: Vault namespace (for enterprise)
        """
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.vault_path = vault_path
        self.namespace = namespace
        self._client: hvac.Client | None = None
        self._secrets_cache: dict[str, Any] = {}
        self._connected = False
    
    @property
    def client(self) -> "hvac.Client | None":
        """Get or create Vault client."""
        if not VAULT_AVAILABLE:
            return None
        
        if self._client is None and self.vault_token:
            try:
                self._client = hvac.Client(
                    url=self.vault_addr,
                    token=self.vault_token,
                    namespace=self.namespace,
                )
                if self._client.is_authenticated():
                    self._connected = True
                    logger.info(f"Connected to Vault at {self.vault_addr}")
                else:
                    logger.warning("Vault authentication failed")
                    self._client = None
            except Exception as e:
                logger.warning(f"Failed to connect to Vault: {e}")
                self._client = None
        
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Vault."""
        return self._connected and self.client is not None
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get a secret value.
        
        First tries Vault, then falls back to environment variables.
        
        Args:
            key: Secret key name
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        # Try cache first
        if key in self._secrets_cache:
            return self._secrets_cache[key]
        
        # Try Vault
        if self.is_connected:
            try:
                secrets = self._fetch_all_secrets()
                if key in secrets:
                    return secrets[key]
            except Exception as e:
                logger.debug(f"Vault lookup failed for {key}: {e}")
        
        # Fall back to environment variable
        value = os.getenv(key, default)
        if value is not None:
            self._secrets_cache[key] = value
        
        return value
    
    def get_secrets(self, keys: list[str] | None = None) -> dict[str, Any]:
        """
        Get multiple secrets.
        
        Args:
            keys: List of keys to retrieve. If None, returns all secrets.
            
        Returns:
            Dictionary of secrets
        """
        all_secrets = self._fetch_all_secrets()
        
        if keys is None:
            return all_secrets
        
        return {k: all_secrets.get(k, os.getenv(k)) for k in keys}
    
    def _fetch_all_secrets(self) -> dict[str, Any]:
        """Fetch all secrets from Vault."""
        if self._secrets_cache:
            return self._secrets_cache
        
        if not self.is_connected:
            return {}
        
        try:
            # Read from KV v2 secrets engine
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.vault_path.replace("secret/data/", ""),
                mount_point="secret",
            )
            
            if response and "data" in response and "data" in response["data"]:
                self._secrets_cache = response["data"]["data"]
                logger.info(f"Loaded {len(self._secrets_cache)} secrets from Vault")
                return self._secrets_cache
                
        except Exception as e:
            logger.debug(f"Failed to fetch secrets from Vault: {e}")
        
        return {}
    
    def set_secret(self, key: str, value: str) -> bool:
        """
        Store a secret in Vault.
        
        Args:
            key: Secret key
            value: Secret value
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.warning("Cannot set secret: not connected to Vault")
            return False
        
        try:
            # Get existing secrets
            current = self._fetch_all_secrets()
            current[key] = value
            
            # Write back
            self.client.secrets.kv.v2.create_or_update_secret(
                path=self.vault_path.replace("secret/data/", ""),
                secret=current,
                mount_point="secret",
            )
            
            # Update cache
            self._secrets_cache[key] = value
            logger.info(f"Stored secret: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set secret {key}: {e}")
            return False
    
    def health_check(self) -> dict:
        """Check Vault connection status."""
        return {
            "vault_available": VAULT_AVAILABLE,
            "vault_addr": self.vault_addr,
            "connected": self.is_connected,
            "secrets_cached": len(self._secrets_cache),
            "using_fallback": not self.is_connected,
        }


# Global client instance
_vault_client: VaultClient | None = None


def get_vault_client(force_reconnect: bool = False) -> VaultClient:
    """Get or create the global Vault client."""
    global _vault_client
    if _vault_client is None or force_reconnect:
        _vault_client = VaultClient()
        # Force connection attempt
        _ = _vault_client.client
    return _vault_client


def get_secret(key: str, default: Any = None) -> Any:
    """
    Get a secret from Vault or environment.
    
    Args:
        key: Secret key name
        default: Default value if not found
        
    Returns:
        Secret value
    """
    return get_vault_client().get_secret(key, default)


def get_secrets(keys: list[str] | None = None) -> dict[str, Any]:
    """
    Get multiple secrets.
    
    Args:
        keys: List of keys, or None for all
        
    Returns:
        Dictionary of secrets
    """
    return get_vault_client().get_secrets(keys)


def vault_health() -> dict:
    """Get Vault health status."""
    return get_vault_client().health_check()
