"""Tests for the RAG pipeline components."""

import pytest
from pathlib import Path
import tempfile

from src.models.schemas import ClinicalDocument, SourceType
from src.rag.loader import DocumentLoader, DocumentChunker


class TestDocumentLoader:
    """Test cases for DocumentLoader."""
    
    @pytest.fixture
    def loader(self):
        """Create a loader instance."""
        return DocumentLoader()
    
    def test_load_from_text(self, loader):
        """Test loading a document from text."""
        text = "Patient presents with diabetes. HbA1c: 7.5%"
        
        doc = loader.load_from_text(
            text=text,
            patient_id="test_123",
            source_type=SourceType.PROGRESS_NOTE,
            document_date="2025-12-15",
        )
        
        assert doc.content == text  # No PII to mask
        assert doc.patient_id.startswith("P")  # Pseudonymized
        assert doc.source_type == SourceType.PROGRESS_NOTE
        assert doc.date == "2025-12-15"
    
    def test_load_with_pii_masking(self, loader):
        """Test that PII is masked when loading."""
        text = "Patient: John Doe. Email: john@example.com"
        
        doc = loader.load_from_text(
            text=text,
            patient_id="test_123",
        )
        
        assert "[PATIENT_NAME]" in doc.content or "[EMAIL]" in doc.content
        assert doc.is_masked is True
    
    def test_load_from_json(self, loader):
        """Test loading documents from JSON."""
        # Create a temporary JSON file
        json_content = '''[
            {"content": "Test document 1", "patient_id": "p1"},
            {"content": "Test document 2", "patient_id": "p2"}
        ]'''
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(json_content)
            temp_path = Path(f.name)
        
        try:
            docs = list(loader.load_from_json(temp_path))
            
            assert len(docs) == 2
            assert docs[0].content == "Test document 1"
            assert docs[1].content == "Test document 2"
        finally:
            temp_path.unlink()


class TestDocumentChunker:
    """Test cases for DocumentChunker."""
    
    @pytest.fixture
    def chunker(self):
        """Create a chunker instance."""
        return DocumentChunker(chunk_size=100, chunk_overlap=20)
    
    @pytest.fixture
    def sample_document(self):
        """Create a sample document for testing."""
        return ClinicalDocument(
            document_id="DOC-TEST",
            patient_id="P12345678901",
            content="This is a test document. " * 20,  # Long enough to chunk
            source_type=SourceType.PROGRESS_NOTE,
        )
    
    def test_chunk_small_document(self, chunker):
        """Test that small documents are not split."""
        doc = ClinicalDocument(
            document_id="DOC-SMALL",
            patient_id="P12345678901",
            content="Short content.",
            source_type=SourceType.PROGRESS_NOTE,
        )
        
        chunks = chunker.chunk_document(doc)
        
        assert len(chunks) == 1
        assert chunks[0].content == "Short content."
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1
    
    def test_chunk_large_document(self, chunker, sample_document):
        """Test that large documents are split into chunks."""
        chunks = chunker.chunk_document(sample_document)
        
        assert len(chunks) > 1
        
        # Check chunk IDs
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)
            assert chunk.document_id == "DOC-TEST"
    
    def test_chunk_metadata_preserved(self, chunker, sample_document):
        """Test that document metadata is preserved in chunks."""
        sample_document.metadata = {"test_key": "test_value"}
        
        chunks = chunker.chunk_document(sample_document)
        
        for chunk in chunks:
            assert chunk.patient_id == sample_document.patient_id
            assert chunk.source_type == sample_document.source_type


class TestRAGIntegration:
    """Integration tests for the RAG pipeline."""
    
    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for the vector store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_ingest_and_retrieve(self, temp_store_path):
        """Test ingesting a document and retrieving it."""
        # Skip if sentence-transformers not available
        pytest.importorskip("sentence_transformers")
        pytest.importorskip("faiss")
        
        from src.rag.vector_store import VectorStore
        from src.rag.embeddings import SentenceTransformerEmbeddings
        
        # Create store with temp path
        embeddings = SentenceTransformerEmbeddings()
        store = VectorStore(embeddings=embeddings, store_path=temp_store_path)
        
        # Create and add a chunk
        from src.models.schemas import DocumentChunk
        chunk = DocumentChunk(
            chunk_id="TEST-C0001",
            document_id="TEST-DOC",
            patient_id="P12345678901",
            content="The patient has Type 2 Diabetes with HbA1c of 7.5%",
            source_type=SourceType.PROGRESS_NOTE,
            chunk_index=0,
            total_chunks=1,
        )
        
        store.add_chunks([chunk])
        
        # Search
        results = store.search("What is the HbA1c level?", top_k=1)
        
        assert len(results) == 1
        assert results[0][0].chunk_id == "TEST-C0001"
        assert results[0][1] > 0  # Score should be positive
