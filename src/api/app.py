"""
FastAPI application factory.

Creates and configures the FastAPI application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.api.routes import (
    health_router, 
    documents_router, 
    query_router, 
    data_router, 
    vault_router,
    databricks_router,
    onprem_router,
    crew_router,
    extraction_router,
)
from src.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"PII Masking: {'enabled' if settings.enable_pii_masking else 'DISABLED'}")
    
    # Load Vault secrets into environment BEFORE RAG pipeline initialization
    _load_vault_secrets()
    
    # Initialize RAG pipeline (lazy loading)
    from src.rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    logger.info(f"Vector store loaded: {pipeline.chunk_count} chunks")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


def _load_vault_secrets():
    """Load secrets from Vault into environment variables."""
    import os
    try:
        import hvac
        vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN", "dev-token-medical")
        
        client = hvac.Client(url=vault_addr, token=vault_token)
        if client.is_authenticated():
            response = client.secrets.kv.v2.read_secret_version(
                path="medical-assistant",
                mount_point="secret"
            )
            secrets = response.get("data", {}).get("data", {})
            
            # Set AWS credentials
            if secrets.get("AWS_ACCESS_KEY_ID"):
                os.environ["AWS_ACCESS_KEY_ID"] = secrets["AWS_ACCESS_KEY_ID"]
            if secrets.get("AWS_SECRET_ACCESS_KEY"):
                os.environ["AWS_SECRET_ACCESS_KEY"] = secrets["AWS_SECRET_ACCESS_KEY"]
            if secrets.get("AWS_DEFAULT_REGION"):
                os.environ["AWS_DEFAULT_REGION"] = secrets["AWS_DEFAULT_REGION"]
            
            logger.info("Loaded secrets from Vault")
        else:
            logger.warning("Vault not authenticated - using local embeddings")
    except Exception as e:
        logger.warning(f"Could not load Vault secrets: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.app_name,
        description="""
        AI Clinical Documentation Assistant
        
        A healthcare-grade AI system for extracting structured information
        from clinical notes. Features:
        
        - **RAG Pipeline**: Semantic search over clinical documents
        - **PII Masking**: Automatic de-identification of sensitive data
        - **Agent Workflow**: Multi-step extraction with validation
        - **JSON Output**: Structured, auditable extraction results
        
        ⚠️ **Important**: AI output is always reviewed by clinicians.
        This system assists with documentation only.
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    cors_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(query_router)
    app.include_router(data_router)
    app.include_router(vault_router)
    app.include_router(databricks_router)
    app.include_router(onprem_router)
    app.include_router(crew_router)
    app.include_router(extraction_router)
    
    return app


# Create the application instance
app = create_app()
