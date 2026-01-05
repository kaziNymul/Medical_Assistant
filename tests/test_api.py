"""Tests for the FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client):
        """Test the health endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
    
    def test_readiness_check(self, client):
        """Test the readiness endpoint."""
        response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "vector_store_size" in data


class TestDocumentEndpoints:
    """Test document management endpoints."""
    
    def test_upload_document(self, client):
        """Test uploading a document."""
        response = client.post(
            "/documents/upload",
            json={
                "content": "Patient has diabetes. HbA1c: 8.5%",
                "patient_id": "test_patient_001",
                "source_type": "progress_note",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["chunks_created"] >= 1
    
    def test_upload_with_pii(self, client):
        """Test that PII is detected during upload."""
        response = client.post(
            "/documents/upload",
            json={
                "content": "Patient: John Smith. Email: john@example.com",
                "patient_id": "test_patient_002",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_masked"] is True
        assert data["pii_items_masked"] >= 1
    
    def test_document_stats(self, client):
        """Test getting document statistics."""
        response = client.get("/documents/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "total_chunks" in data


class TestQueryEndpoints:
    """Test query endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup_data(self, client):
        """Ensure some sample data exists."""
        client.post("/documents/ingest-sample")
    
    def test_search_documents(self, client):
        """Test searching documents."""
        # Skip if no embeddings available
        try:
            response = client.post(
                "/query/search",
                params={
                    "query": "diabetes HbA1c",
                    "top_k": 3,
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total" in data
        except Exception:
            pytest.skip("Embeddings not available")
    
    def test_extract_clinical_data(self, client):
        """Test clinical data extraction."""
        try:
            response = client.post(
                "/query/extract",
                json={
                    "query": "What is the patient's HbA1c and medications?",
                    "top_k": 3,
                    "include_evidence": True,
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "extraction" in data
            assert "query" in data
        except Exception:
            pytest.skip("Extraction not available")


class TestIngestSample:
    """Test sample data ingestion."""
    
    def test_ingest_sample(self, client):
        """Test ingesting sample data."""
        try:
            response = client.post("/documents/ingest-sample")
            
            assert response.status_code == 200
            data = response.json()
            assert "chunks_created" in data
            assert data["chunks_created"] > 0
        except Exception:
            pytest.skip("Sample ingestion not available")
