"""
Configuration settings for the Medical Assistant.

Uses Pydantic Settings with HashiCorp Vault integration.
Secrets are fetched from Vault first, with env fallback.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    """Application settings loaded from Vault and environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "AI Clinical Documentation Assistant"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # RAG Settings
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    vector_store_path: str = "./data/vector_store"
    
    # LLM Provider
    llm_provider: Literal["local", "bedrock"] = "local"
    
    # AWS Bedrock (Phase 2) - fetched from Vault
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"
    
    # Databricks (Phase 3) - fetched from Vault
    databricks_host: str | None = None
    databricks_token: str | None = None
    databricks_catalog: str = "healthcare_ai"
    databricks_schema: str = "clinical_docs"
    
    # HashiCorp Vault
    vault_addr: str = "http://127.0.0.1:8200"
    vault_token: str | None = None
    vault_path: str = "secret/data/medical-assistant"
    vault_enabled: bool = True
    
    # Security
    enable_pii_masking: bool = True
    min_confidence_threshold: float = 0.7
    
    # UI Settings
    ui_enabled: bool = True
    cors_origins: str = "*"
    
    @model_validator(mode="after")
    def load_vault_secrets(self) -> "Settings":
        """Load secrets from Vault after initial settings load."""
        if not self.vault_enabled:
            return self
        
        try:
            from src.utils.vault import get_vault_client
            
            vault = get_vault_client()
            if vault.is_connected:
                # Override with Vault secrets if available
                secrets = vault.get_secrets()
                
                if "AWS_ACCESS_KEY_ID" in secrets:
                    object.__setattr__(self, "aws_access_key_id", secrets["AWS_ACCESS_KEY_ID"])
                if "AWS_SECRET_ACCESS_KEY" in secrets:
                    object.__setattr__(self, "aws_secret_access_key", secrets["AWS_SECRET_ACCESS_KEY"])
                if "AWS_REGION" in secrets:
                    object.__setattr__(self, "aws_region", secrets["AWS_REGION"])
                if "DATABRICKS_HOST" in secrets:
                    object.__setattr__(self, "databricks_host", secrets["DATABRICKS_HOST"])
                if "DATABRICKS_TOKEN" in secrets:
                    object.__setattr__(self, "databricks_token", secrets["DATABRICKS_TOKEN"])
                    
        except ImportError:
            pass  # Vault module not loaded yet during initial import
        except Exception:
            pass  # Vault not available, use env vars
        
        return self
    
    @property
    def base_path(self) -> Path:
        """Get the base path of the project."""
        return Path(__file__).parent.parent
    
    @property
    def data_path(self) -> Path:
        """Get the data directory path."""
        return self.base_path / "data"
    
    @property
    def vector_store_full_path(self) -> Path:
        """Get the full path to vector store."""
        return Path(self.vector_store_path)
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"
    
    def is_bedrock_enabled(self) -> bool:
        """Check if AWS Bedrock is configured."""
        return (
            self.llm_provider == "bedrock"
            and self.aws_access_key_id is not None
            and self.aws_secret_access_key is not None
        )
    
    def is_databricks_enabled(self) -> bool:
        """Check if Databricks is configured."""
        return (
            self.databricks_host is not None
            and self.databricks_token is not None
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
