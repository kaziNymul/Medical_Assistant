"""
FastAPI routes for the Medical Assistant.

Provides REST API endpoints for:
- Document upload and processing
- Clinical queries and extraction
- Health checks
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from config.settings import settings
from src.agents.workflow import get_workflow
from src.data.processor import get_processor, process_all_data, get_data_status
from src.models.schemas import (
    ClinicalExtraction,
    DocumentUploadRequest,
    DocumentUploadResponse,
    HealthCheckResponse,
    QueryRequest,
    QueryResponse,
    SourceType,
)
from src.rag.pipeline import get_rag_pipeline
from src.utils.logging import logger, log_query
from src.utils.masking import get_masker
from src.utils.vault import vault_health

import hashlib


# Create routers
health_router = APIRouter(tags=["Health"])
documents_router = APIRouter(prefix="/documents", tags=["Documents"])
query_router = APIRouter(prefix="/query", tags=["Query"])
data_router = APIRouter(prefix="/data", tags=["Data Pipeline"])
vault_router = APIRouter(prefix="/vault", tags=["Secrets Management"])
extraction_router = APIRouter(prefix="/extract", tags=["Intelligent Extraction"])


# ====================
# Health Check Routes
# ====================

@health_router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Check if the service is healthy."""
    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.app_env,
        timestamp=datetime.utcnow(),
    )


@health_router.get("/ready")
async def readiness_check():
    """Check if the service is ready to accept requests."""
    pipeline = get_rag_pipeline()
    
    return {
        "ready": True,
        "vector_store_size": pipeline.chunk_count,
        "document_count": pipeline.document_count,
    }


# ====================
# Document Routes
# ====================

@documents_router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(request: DocumentUploadRequest):
    """
    Upload and process a clinical document.
    
    The document will be:
    1. Masked for PII
    2. Chunked for RAG
    3. Embedded and indexed
    """
    try:
        pipeline = get_rag_pipeline()
        masker = get_masker()
        
        # Check for PII in the input
        mask_result = masker.mask_text(request.content)
        
        # Ingest the document
        document_id, chunks_created = pipeline.ingest_document(
            text=request.content,
            patient_id=request.patient_id,
            source_type=request.source_type,
            document_date=request.document_date,
        )
        
        logger.info(f"Document uploaded: {document_id} with {chunks_created} chunks")
        
        return DocumentUploadResponse(
            document_id=document_id,
            chunks_created=chunks_created,
            is_masked=mask_result.pii_detected,
            pii_items_masked=mask_result.items_masked,
            message=f"Document processed successfully. {mask_result.items_masked} PII items masked.",
        )
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@documents_router.post("/upload-file")
async def upload_document_file(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    source_type: str = Form(default="unknown"),
):
    """
    Upload a clinical document from a file.
    
    Supports text files (.txt, .md).
    """
    # Validate file type
    allowed_extensions = [".txt", ".md", ".text"]
    file_ext = Path(file.filename or "").suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {allowed_extensions}",
        )
    
    try:
        # Read file content
        content = await file.read()
        text = content.decode("utf-8")
        
        # Determine source type
        try:
            src_type = SourceType(source_type.lower())
        except ValueError:
            src_type = SourceType.UNKNOWN
        
        # Process
        pipeline = get_rag_pipeline()
        document_id, chunks_created = pipeline.ingest_document(
            text=text,
            patient_id=patient_id,
            source_type=src_type,
        )
        
        return DocumentUploadResponse(
            document_id=document_id,
            chunks_created=chunks_created,
            is_masked=True,
            message=f"File '{file.filename}' processed successfully.",
        )
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@documents_router.get("/stats")
async def get_document_stats():
    """Get statistics about indexed documents."""
    pipeline = get_rag_pipeline()
    
    return {
        "total_documents": pipeline.document_count,
        "total_chunks": pipeline.chunk_count,
        "vector_store_path": str(pipeline.vector_store.store_path),
    }


@documents_router.delete("/clear")
async def clear_documents():
    """Clear all indexed documents."""
    pipeline = get_rag_pipeline()
    pipeline.vector_store.clear()
    
    return {"message": "All documents cleared", "success": True}


# ====================
# Query Routes
# ====================

@query_router.post("/extract", response_model=QueryResponse)
async def extract_clinical_data(request: QueryRequest):
    """
    Query indexed documents and extract clinical data.
    
    Uses the agent workflow to:
    1. Retrieve relevant chunks
    2. Extract structured data
    3. Validate extraction
    4. Generate explanation
    """
    try:
        workflow = get_workflow()
        
        # Run extraction
        response = workflow.extract(
            query=request.query,
            patient_id=request.patient_id,
        )
        
        # Log query (without actual content)
        query_hash = hashlib.sha256(request.query.encode()).hexdigest()
        log_query(
            query_hash=query_hash,
            num_results=len(response.retrieved_chunks),
            processing_time_ms=response.processing_time_ms,
        )
        
        # Optionally remove chunks from response
        if not request.include_evidence:
            response.retrieved_chunks = []
        
        return response
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@query_router.post("/search")
async def search_documents(
    query: str,
    top_k: int = 5,
    patient_id: Optional[str] = None,
):
    """
    Search for relevant document chunks.
    
    Returns raw chunks without extraction.
    """
    try:
        pipeline = get_rag_pipeline()
        
        results = pipeline.retrieve(
            query=query,
            top_k=top_k,
            patient_id=patient_id,
        )
        
        return {
            "query": query,
            "results": [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "score": score,
                    "source_type": chunk.source_type.value,
                }
                for chunk, score in results
            ],
            "total": len(results),
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Utility Routes
# ====================

@documents_router.post("/ingest-sample")
async def ingest_sample_data():
    """
    Ingest sample clinical data from Kaggle datasets.
    
    First download data using:
        python scripts/download_kaggle_data.py --dataset healthcare
    
    Then call this endpoint to ingest the processed JSON files.
    """
    try:
        pipeline = get_rag_pipeline()
        sample_dir = Path("data/sample")
        
        total_chunks = 0
        files_processed = []
        
        if sample_dir.exists():
            # Try to ingest CSV files (Kaggle raw data)
            for csv_file in sample_dir.glob("*.csv"):
                try:
                    chunks = pipeline.ingest_csv(csv_file)
                    total_chunks += chunks
                    files_processed.append(str(csv_file.name))
                except Exception as e:
                    logger.warning(f"Failed to ingest {csv_file}: {e}")
            
            # Try to ingest JSON files (processed Kaggle data)
            for json_file in sample_dir.glob("*.json"):
                try:
                    chunks = pipeline.ingest_json(json_file)
                    total_chunks += chunks
                    files_processed.append(str(json_file.name))
                except Exception as e:
                    logger.warning(f"Failed to ingest {json_file}: {e}")
        
        if total_chunks == 0:
            return {
                "message": "No data found. Please download Kaggle data first.",
                "instructions": [
                    "1. pip install kaggle",
                    "2. Setup Kaggle API: https://www.kaggle.com/settings -> Create API Token",
                    "3. python scripts/download_kaggle_data.py --dataset healthcare",
                    "4. Call this endpoint again"
                ],
                "chunks_created": 0,
                "total_chunks": pipeline.chunk_count,
            }
        
        return {
            "message": "Kaggle data ingested successfully",
            "files_processed": files_processed,
            "chunks_created": total_chunks,
            "total_chunks": pipeline.chunk_count,
        }
        
    except Exception as e:
        logger.error(f"Sample ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Data Pipeline Routes
# ====================

@data_router.get("/status")
async def get_pipeline_status():
    """
    Get the status of the data processing pipeline.
    
    Shows:
    - Raw datasets available (Bronze layer)
    - Processed files (Silver layer)
    - AI-ready files (Gold layer)
    """
    try:
        status = get_data_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get data status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@data_router.post("/process")
async def process_raw_data(dataset: Optional[str] = None, force: bool = False):
    """
    Process raw data through the Bronze → Silver → Gold pipeline.
    
    This applies PII masking and transforms data for AI consumption.
    
    Args:
        dataset: Optional specific dataset to process. If not provided, processes all.
        force: If True, reprocess even if already processed.
    """
    try:
        processor = get_processor()
        
        if dataset:
            # Process specific dataset
            result = processor.process_dataset(dataset)
        else:
            # Process all
            result = processor.process_all()
        
        return result
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@data_router.get("/raw")
async def list_raw_data():
    """
    List all raw (Bronze layer) datasets available for processing.
    """
    try:
        processor = get_processor()
        datasets = processor.get_raw_datasets()
        
        return {
            "datasets": datasets,
            "total": len(datasets),
            "download_command": "python scripts/download_kaggle_data.py --dataset <name>",
        }
        
    except Exception as e:
        logger.error(f"Failed to list raw data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@data_router.post("/ingest")
async def ingest_processed_data():
    """
    Ingest processed (Gold layer) data into the RAG vector store.
    
    This loads the AI-ready JSON files into the vector store for querying.
    """
    try:
        pipeline = get_rag_pipeline()
        ai_ready_dir = Path("data/ai_ready")
        
        if not ai_ready_dir.exists():
            return {
                "success": False,
                "message": "No AI-ready data found. Run /data/process first.",
                "steps": [
                    "1. Download raw data: python scripts/download_kaggle_data.py --dataset healthcare",
                    "2. Process raw data: POST /data/process",
                    "3. Ingest into RAG: POST /data/ingest",
                ],
            }
        
        total_chunks = 0
        files_processed = []
        
        for json_file in ai_ready_dir.glob("*_gold.json"):
            try:
                chunks = pipeline.ingest_gold_json(json_file)
                total_chunks += chunks
                files_processed.append(json_file.name)
            except Exception as e:
                logger.warning(f"Failed to ingest {json_file}: {e}")
        
        return {
            "success": True,
            "message": "Gold layer data ingested into RAG",
            "files_processed": files_processed,
            "chunks_created": total_chunks,
            "total_chunks": pipeline.chunk_count,
        }
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@data_router.get("/sample/{layer}")
async def get_sample_data(layer: str, limit: int = 5):
    """
    Get sample records from a specific data layer.
    
    Args:
        layer: One of 'raw', 'processed', 'ai_ready'
        limit: Number of sample records to return
    """
    try:
        import json
        
        if layer == "raw":
            data_dir = Path("data/raw/kaggle")
        elif layer == "processed":
            data_dir = Path("data/processed")
        elif layer == "ai_ready":
            data_dir = Path("data/ai_ready")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid layer. Use: raw, processed, ai_ready"
            )
        
        if not data_dir.exists():
            return {"samples": [], "message": f"No data in {layer} layer"}
        
        samples = []
        
        # For raw, look for CSV files
        if layer == "raw":
            import csv
            for dataset_dir in data_dir.iterdir():
                if not dataset_dir.is_dir():
                    continue
                for csv_file in dataset_dir.glob("*.csv"):
                    with open(csv_file, newline='') as f:
                        reader = csv.DictReader(f)
                        for i, row in enumerate(reader):
                            if i >= limit:
                                break
                            samples.append({
                                "source": f"{dataset_dir.name}/{csv_file.name}",
                                "data": row,
                            })
                    if samples:
                        break
                if samples:
                    break
        else:
            # For processed/ai_ready, read JSON files
            for json_file in data_dir.glob("*.json"):
                with open(json_file) as f:
                    data = json.load(f)
                
                records = data.get("records", data.get("documents", []))[:limit]
                for record in records:
                    samples.append({
                        "source": json_file.name,
                        "data": record,
                    })
                if samples:
                    break
        
        return {
            "layer": layer,
            "samples": samples[:limit],
            "total_samples": len(samples),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get samples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Vault Routes
# ====================

@vault_router.get("/status")
async def get_vault_status():
    """
    Get HashiCorp Vault connection status.
    
    Returns information about:
    - Vault availability
    - Connection status
    - Secrets caching
    """
    try:
        status = vault_health()
        return status
    except Exception as e:
        return {
            "vault_available": False,
            "connected": False,
            "error": str(e),
        }


# ====================
# Patient Data Routes (Optimized PII-Only Storage)
# ====================

onprem_router = APIRouter(prefix="/onprem", tags=["Patient Data (Hybrid Storage)"])


def _get_medical_data_from_cloud(record_id: str) -> dict:
    """
    Get non-PII medical data from cloud storage (masked JSON/FAISS).
    
    This data includes: diagnosis, medications, test results, etc.
    (Everything except Name, Doctor, Hospital, Insurance)
    """
    import json
    from pathlib import Path
    
    # Search masked JSON files for this record_id
    masked_dir = Path("data/ai_ready")
    for json_file in masked_dir.glob("*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if data.get('metadata', {}).get('record_id') == record_id:
                    # Return masked content (medical data without PII)
                    return {
                        "masked_content": data.get("content", ""),
                        "source_file": json_file.name,
                        "medical_data": data.get("metadata", {}),
                    }
        except:
            continue
    return {}


@onprem_router.get("/patient/{record_id}")
async def get_original_patient_data(
    record_id: str,
    accessed_by: str = "clinician",
    access_reason: str = "clinical_review"
):
    """
    Retrieve ORIGINAL (unmasked) patient data.
    
    Optimized hybrid architecture:
    - PII (Name, Doctor, Hospital, Insurance) from local PII-only database
    - Medical data (diagnosis, meds, tests) from cloud masked storage
    - Merged together for display
    
    Security:
    - All access is logged for HIPAA audit compliance
    - PII stored separately in minimal local database
    - Medical data (non-PII) stored in cloud
    
    Args:
        record_id: Unique record ID (e.g., "rec_a1b2c3d4-...")
        accessed_by: User/system making the request (logged)
        access_reason: Reason for access (logged)
    
    Returns:
        Merged patient data with full PII and medical info
    """
    try:
        # Try new PII-only database first
        from src.data.pii_db import get_pii_db
        
        pii_db = get_pii_db()
        pii_data = pii_db.get_pii(
            record_id=record_id,
            accessed_by=accessed_by,
            access_reason=access_reason,
        )
        
        if pii_data:
            # Get medical data from cloud
            medical_data = _get_medical_data_from_cloud(record_id)
            
            return {
                "success": True,
                "record_id": record_id,
                "patient_name": pii_data.get("patient_name"),
                "doctor_name": pii_data.get("doctor_name"),
                "hospital_name": pii_data.get("hospital_name"),
                "insurance_provider": pii_data.get("insurance_provider"),
                "source_file": pii_data.get("source_file"),
                "medical_data": medical_data.get("masked_content", ""),
                "storage_mode": "pii_optimized",
                "access_logged": True,
            }
        
        # Fallback to old storage system
        from src.databricks.patient_storage import get_patient_storage
        
        storage = get_patient_storage()
        record = storage.get_original_patient(
            record_id=record_id,
            accessed_by=accessed_by,
            access_reason=access_reason,
        )
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")
        
        return {
            "success": True,
            "record_id": record_id,
            "original_data": record.get("original_data", {}),
            "patient_name": record.get("patient_name"),
            "doctor_name": record.get("doctor_name"),
            "hospital_name": record.get("hospital_name"),
            "source_file": record.get("source_file"),
            "storage_mode": storage.get_stats().get("mode", "legacy"),
            "access_logged": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get original patient data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@onprem_router.post("/patients/batch")
async def get_original_patients_batch(record_ids: list[str], accessed_by: str = "clinician"):
    """
    Retrieve multiple original patient records in a batch.
    
    Used when AI returns multiple documents - fetch all originals at once.
    
    Args:
        record_ids: List of record IDs to fetch
        accessed_by: User making the request
    
    Returns:
        Dictionary mapping record_id to original data
    """
    try:
        from src.data.onprem_db import get_onprem_db
        
        db = get_onprem_db()
        results = db.get_original_by_ids(record_ids, accessed_by)
        
        return {
            "success": True,
            "records": results,
            "found": len(results),
            "requested": len(record_ids),
        }
    except Exception as e:
        logger.error(f"Failed to get batch patient data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@onprem_router.get("/patient/{record_id}/audit")
async def get_patient_access_log(record_id: str, limit: int = 100):
    """
    Get access audit log for a patient record.
    
    For HIPAA compliance - shows who accessed the record and when.
    """
    try:
        from src.data.onprem_db import get_onprem_db
        
        db = get_onprem_db()
        log = db.get_access_log(record_id, limit)
        
        return {
            "record_id": record_id,
            "access_log": log,
            "total_accesses": len(log),
        }
    except Exception as e:
        logger.error(f"Failed to get access log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@onprem_router.get("/stats")
async def get_storage_stats():
    """
    Get hybrid storage statistics (Local + Databricks).
    """
    try:
        from src.databricks.patient_storage import get_patient_storage
        
        storage = get_patient_storage()
        stats = storage.get_stats()
        
        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Databricks Routes (Phase 3)
# ====================

databricks_router = APIRouter(prefix="/databricks", tags=["Databricks"])


@databricks_router.get("/status")
async def get_databricks_status():
    """
    Get Databricks connection status.
    
    Returns information about:
    - Connection status
    - Current user
    - Available clusters/warehouses
    """
    try:
        from src.databricks.client import get_databricks_client
        
        client = get_databricks_client()
        
        if not client.is_connected:
            return {
                "connected": False,
                "error": "Not connected to Databricks",
            }
        
        return {
            "connected": True,
            "user": client.get_current_user(),
            "clusters": client.list_clusters(),
            "warehouses": client.list_warehouses(),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


@databricks_router.get("/logs")
async def get_ai_logs(limit: int = 100):
    """
    Get AI query logs.
    
    Returns recent AI queries and responses for monitoring.
    """
    try:
        from src.databricks.logging import get_ai_logger
        
        ai_logger = get_ai_logger()
        
        return {
            "logs": ai_logger.get_local_logs()[-limit:],
            "stats": ai_logger.get_stats(),
        }
    except Exception as e:
        logger.error(f"Failed to get AI logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@databricks_router.get("/metrics")
async def get_ai_metrics():
    """
    Get AI evaluation metrics summary.
    """
    try:
        from src.databricks.logging import get_ai_logger
        
        ai_logger = get_ai_logger()
        
        return {
            "metrics": ai_logger.get_local_metrics(),
            "stats": ai_logger.get_stats(),
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@databricks_router.post("/feedback/{query_id}")
async def submit_feedback(query_id: str, feedback: str = "positive"):
    """
    Submit user feedback for a query.
    
    Args:
        query_id: The query ID to provide feedback for
        feedback: "positive", "negative", or "neutral"
    """
    try:
        from src.databricks.logging import get_ai_logger
        
        ai_logger = get_ai_logger()
        success = ai_logger.log_feedback(query_id, feedback)
        
        return {
            "success": success,
            "query_id": query_id,
            "feedback": feedback,
        }
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@databricks_router.post("/sync")
async def sync_to_databricks(dry_run: bool = False):
    """
    Sync PII data to Databricks.
    
    Args:
        dry_run: If True, only report what would be synced
    """
    try:
        import subprocess
        import sys
        
        script_path = Path(__file__).parent.parent.parent / "scripts" / "sync_to_databricks.py"
        
        if not script_path.exists():
            raise HTTPException(status_code=404, detail="Sync script not found")
        
        cmd = [sys.executable, str(script_path)]
        if dry_run:
            cmd.append("--dry-run")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr or "Sync failed",
                "dry_run": dry_run,
            }
        
        return {
            "success": True,
            "output": result.stdout,
            "dry_run": dry_run,
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Sync timed out after 5 minutes")
    except Exception as e:
        logger.error(f"Databricks sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# CrewAI Routes
# ====================

crew_router = APIRouter(prefix="/crew", tags=["CrewAI Agents"])


@crew_router.post("/case-brief")
async def generate_case_brief(
    query: str,
    patient_id: Optional[str] = None,
):
    """
    Generate a full clinical case brief using the 5-agent CrewAI workflow.
    
    This runs all 5 agents:
    1. Medical Record Retriever
    2. Clinical Information Extractor
    3. Risk & Trend Analyst
    4. Clinical Gaps Finder
    5. Case Brief Writer
    
    Returns a comprehensive case briefing for physician review.
    """
    try:
        from src.crew import get_clinical_crew
        
        crew = get_clinical_crew()
        result = await crew.arun(query=query, patient_id=patient_id)
        
        return result
        
    except Exception as e:
        logger.error(f"CrewAI case brief failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@crew_router.post("/quick-extract")
async def quick_extraction(
    query: str,
    patient_id: Optional[str] = None,
):
    """
    Quick clinical data extraction using simplified 2-agent workflow.
    
    Uses only:
    1. Retriever Agent
    2. Extractor Agent
    
    Faster than full case brief but less comprehensive.
    """
    try:
        from src.crew import get_quick_crew
        
        crew = get_quick_crew()
        
        # Run in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: crew.run(query, patient_id)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Quick extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@crew_router.get("/agents")
async def list_agents():
    """
    List all available CrewAI agents and their roles.
    """
    return {
        "agents": [
            {
                "name": "Medical Record Retriever",
                "role": "Retrieve relevant patient records for clinical review",
                "tools": ["rag_search"],
            },
            {
                "name": "Clinical Information Extractor",
                "role": "Extract structured clinical data from patient records",
                "tools": ["extract_clinical_data"],
            },
            {
                "name": "Risk & Trend Analyst",
                "role": "Identify clinical risk signals and trends",
                "tools": ["analyze_clinical_risks"],
            },
            {
                "name": "Clinical Gaps Finder",
                "role": "Find missing or incomplete clinical information",
                "tools": ["find_information_gaps"],
            },
            {
                "name": "Case Brief Writer",
                "role": "Synthesize findings into structured case briefing",
                "tools": [],
            },
        ],
        "workflows": [
            {
                "name": "Full Case Brief",
                "endpoint": "/crew/case-brief",
                "agents_used": 5,
                "description": "Complete clinical case briefing with all agents",
            },
            {
                "name": "Quick Extraction",
                "endpoint": "/crew/quick-extract",
                "agents_used": 2,
                "description": "Fast extraction with retriever and extractor only",
            },
        ],
    }


@crew_router.get("/status")
async def crew_status():
    """
    Get CrewAI system status.
    """
    try:
        from src.crew import get_clinical_crew
        
        crew = get_clinical_crew()
        crew._setup()  # Ensure agents are initialized
        
        return {
            "status": "ready",
            "agents_initialized": len(crew._agents) if crew._agents else 0,
            "llm_provider": "bedrock",
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# ====================
# Intelligent Extraction Routes
# ====================

@extraction_router.get("/models")
async def list_extraction_models():
    """List available local LLM models for extraction."""
    current_model = os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
    
    return {
        "available_models": [
            {
                "id": "google/flan-t5-small",
                "name": "FLAN-T5 Small",
                "size": "80MB",
                "ram_required": "1GB",
                "speed": "~3-5 sec",
                "accuracy": "Basic",
                "recommended_for": "Quick tests, very low resources"
            },
            {
                "id": "google/flan-t5-base",
                "name": "FLAN-T5 Base",
                "size": "250MB",
                "ram_required": "2GB",
                "speed": "~5-15 sec",
                "accuracy": "Good",
                "recommended_for": "Production use on CPU - RECOMMENDED",
                "is_default": True
            },
            {
                "id": "google/flan-t5-large",
                "name": "FLAN-T5 Large",
                "size": "780MB",
                "ram_required": "4GB",
                "speed": "~15-45 sec",
                "accuracy": "Better",
                "recommended_for": "Higher accuracy, more RAM needed"
            },
        ],
        "current_model": current_model,
        "device": os.getenv('EXTRACTION_DEVICE', 'cpu'),
        "cache_dir": os.getenv('EXTRACTION_CACHE_DIR', './models'),
        "setup_command": "bash scripts/setup_local_llm.sh"
    }


@extraction_router.get("/status")
async def extraction_status():
    """Check if extraction model is loaded and ready."""
    try:
        from src.extraction.llm_extractor import get_extractor
        extractor = get_extractor()
        
        return {
            "status": "ready" if extractor._loaded else "not_loaded",
            "model": extractor.model_name,
            "device": extractor.device,
            "loaded": extractor._loaded,
            "message": "Model loaded and ready" if extractor._loaded else "Model will load on first extraction"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Run 'bash scripts/setup_local_llm.sh' to install dependencies"
        }


@extraction_router.post("/upload")
async def intelligent_extract_upload(
    file: UploadFile = File(...),
    patient_id: str = Form(default=None),
    sync_to_databricks: bool = Form(default=True),
    model: str = Form(default=None)
):
    """
    Upload ANY file type and intelligently extract clinical data.
    
    Supports:
    - Documents: PDF, Word, TXT, RTF
    - Data: CSV, Excel, JSON, XML
    - Clinical: HL7, FHIR, CDA/CCDA
    - Images: PNG, JPG (with OCR)
    
    Process:
    1. Parse file content (any format)
    2. Use local HuggingFace LLM to extract clinical data
    3. Create masked (de-identified) and unmasked versions
    4. Optionally sync to Databricks
    
    Returns both versions for review.
    """
    try:
        # Read file content
        file_bytes = await file.read()
        filename = file.filename or "unknown"
        
        logger.info(f"Processing file: {filename} ({len(file_bytes)} bytes)")
        
        # Get or create processor
        from src.extraction.llm_extractor import ClinicalDataProcessor
        processor = ClinicalDataProcessor(
            model_name=model or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
        )
        
        # Process and extract
        result = processor.process_and_sync(
            file_bytes=file_bytes,
            filename=filename,
            patient_id=patient_id,
            sync_to_databricks=sync_to_databricks
        )
        
        return {
            "success": True,
            "filename": filename,
            "file_size_bytes": len(file_bytes),
            "extraction": {
                "masked": result['masked'],
                "unmasked": result['unmasked']
            },
            "metadata": result['metadata'],
            "databricks_sync": result.get('databricks_sync'),
            "message": f"Successfully extracted clinical data from {filename}"
        }
        
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency: {e}. Install with: pip install transformers torch"
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@extraction_router.post("/text")
async def intelligent_extract_text(
    text: str = Form(...),
    patient_id: str = Form(default=None),
    sync_to_databricks: bool = Form(default=True),
    model: str = Form(default=None)
):
    """
    Extract clinical data from text content.
    
    Use this for:
    - Pasted clinical notes
    - Text from any source
    - Manual data entry
    """
    try:
        from src.extraction.llm_extractor import LocalLLMExtractor
        from src.utils.masking import get_masker
        from src.utils.databricks_sync import sync_clinical_extraction
        
        # Initialize extractor
        extractor = LocalLLMExtractor(
            model_name=model or os.getenv('EXTRACTION_MODEL', 'google/flan-t5-base')
        )
        masker = get_masker()
        
        # Extract clinical data
        extraction = extractor.extract(text, source_file="text_input")
        if patient_id:
            extraction.patient_id = patient_id
        
        # Create masked/unmasked versions
        unmasked = extraction.to_dict()
        masked = extraction.to_masked_dict(masker)
        
        # Sync to Databricks if requested
        db_result = None
        if sync_to_databricks:
            try:
                db_result = sync_clinical_extraction(unmasked, masked)
            except Exception as e:
                db_result = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "extraction": {
                "masked": masked,
                "unmasked": unmasked
            },
            "databricks_sync": db_result,
            "message": "Successfully extracted clinical data from text"
        }
        
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@extraction_router.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported file formats."""
    from src.extraction.file_parser import UniversalFileParser
    
    parser = UniversalFileParser()
    
    return {
        "supported_extensions": list(parser.SUPPORTED_EXTENSIONS.keys()),
        "format_types": {
            "documents": [".txt", ".md", ".pdf", ".docx", ".doc", ".rtf"],
            "data": [".csv", ".xlsx", ".xls", ".json", ".xml"],
            "clinical_standards": [".hl7", ".fhir", ".cda", ".ccda"],
            "images_ocr": [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        },
        "features": {
            "pdf": parser.has_pdf,
            "word": parser.has_docx,
            "excel": parser.has_pandas and parser.has_openpyxl,
            "ocr": parser.has_ocr
        },
        "install_commands": {
            "pdf": "pip install pypdf",
            "word": "pip install python-docx",
            "excel": "pip install pandas openpyxl",
            "ocr": "pip install pytesseract Pillow (+ install Tesseract OCR)"
        }
    }


@extraction_router.get("/schema")
async def get_extraction_schema():
    """Get the clinical data schema that will be extracted."""
    return {
        "schema": {
            "patient_demographics": {
                "patient_id": "Unique identifier",
                "patient_name": "Full name (PII)",
                "date_of_birth": "DOB in YYYY-MM-DD (PII)",
                "gender": "M/F/Other",
                "age": "Age in years",
                "mrn": "Medical Record Number (PII)",
                "ssn": "Social Security Number (PII)",
                "address": "Full address (PII)",
                "phone": "Phone number (PII)",
                "email": "Email address (PII)",
                "insurance_id": "Insurance ID (PII)"
            },
            "clinical_data": {
                "diagnoses": [{"code": "ICD-10", "description": "text", "type": "primary/secondary"}],
                "medications": [{"name": "drug", "dose": "amount", "frequency": "schedule", "route": "method"}],
                "allergies": [{"allergen": "substance", "reaction": "symptoms", "severity": "level"}],
                "procedures": [{"code": "CPT", "description": "text", "date": "when"}],
                "lab_results": [{"test": "name", "value": "result", "unit": "units", "reference_range": "normal"}],
                "vital_signs": {"bp": "", "hr": "", "temp": "", "resp_rate": "", "spo2": "", "weight": "", "height": ""}
            },
            "visit_info": {
                "visit_date": "Date of visit",
                "visit_type": "Office/ED/Inpatient",
                "chief_complaint": "Primary reason",
                "history_present_illness": "HPI summary"
            },
            "provider_info": {
                "provider_name": "Doctor/Nurse name",
                "provider_npi": "NPI number",
                "facility_name": "Hospital/Clinic"
            },
            "assessment_plan": {
                "assessment": "Clinical assessment",
                "plan": "Treatment plan",
                "follow_up": "Follow-up instructions"
            }
        },
        "pii_fields": [
            "patient_name", "date_of_birth", "ssn", "address",
            "phone", "email", "insurance_id", "mrn", "provider_name"
        ],
        "note": "PII fields are masked in the 'masked' output and stored separately in Databricks"
    }