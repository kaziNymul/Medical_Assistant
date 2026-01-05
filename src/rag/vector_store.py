"""
Vector store implementation using FAISS.

Provides:
- Document indexing
- Similarity search
- Persistence to disk
"""

import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import settings
from src.models.schemas import DocumentChunk
from src.rag.embeddings import BaseEmbeddings, get_embeddings
from src.utils.logging import logger


class VectorStore:
    """
    FAISS-based vector store for RAG.
    
    Stores document chunks with their embeddings for
    efficient similarity search.
    """
    
    def __init__(
        self,
        embeddings: BaseEmbeddings | None = None,
        store_path: Path | None = None,
    ):
        """
        Initialize the vector store.
        
        Args:
            embeddings: Embeddings provider to use.
            store_path: Path to persist the vector store.
        """
        self.embeddings = embeddings or get_embeddings()
        self.store_path = store_path or Path(settings.vector_store_path)
        
        # FAISS index
        self._index = None
        
        # Metadata storage (chunk_id -> DocumentChunk)
        self._chunks: dict[str, DocumentChunk] = {}
        
        # ID mapping (index position -> chunk_id)
        self._id_map: list[str] = []
        
        # Ensure store directory exists
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def _ensure_index(self):
        """Ensure the FAISS index exists."""
        if self._index is None:
            try:
                import faiss
                # Use Inner Product (IP) index - normalize vectors for cosine similarity
                self._index = faiss.IndexFlatIP(self.embeddings.dimension)
                logger.info(f"Created FAISS index with dimension {self.embeddings.dimension}")
            except ImportError:
                raise ImportError(
                    "faiss-cpu is required. Install with: pip install faiss-cpu"
                )
    
    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of DocumentChunk instances to add.
            
        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0
        
        self._ensure_index()
        
        # Extract texts and generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embeddings.embed_texts(texts)
        
        # Normalize for cosine similarity
        faiss = self._get_faiss()
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self._index.add(embeddings)
        
        # Store metadata
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            self._id_map.append(chunk.chunk_id)
        
        logger.info(f"Added {len(chunks)} chunks to vector store")
        return len(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        patient_id: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Search for similar chunks.
        
        Args:
            query: Query text.
            top_k: Number of results to return.
            patient_id: Optional filter by patient ID.
            
        Returns:
            List of (chunk, score) tuples sorted by relevance.
        """
        if self._index is None or self._index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []
        
        # Generate query embedding
        query_embedding = self.embeddings.embed_text(query)
        query_embedding = query_embedding.reshape(1, -1)
        
        # Normalize for cosine similarity
        faiss = self._get_faiss()
        faiss.normalize_L2(query_embedding)
        
        # Search (get more results if filtering by patient)
        search_k = top_k * 3 if patient_id else top_k
        scores, indices = self._index.search(query_embedding, min(search_k, self._index.ntotal))
        
        # Collect results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for missing results
                continue
            
            chunk_id = self._id_map[idx]
            chunk = self._chunks.get(chunk_id)
            
            if chunk is None:
                continue
            
            # Filter by patient if specified
            if patient_id and chunk.patient_id != patient_id:
                continue
            
            results.append((chunk, float(score)))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def get_chunk(self, chunk_id: str) -> DocumentChunk | None:
        """Get a specific chunk by ID."""
        return self._chunks.get(chunk_id)
    
    def get_chunks_by_document(self, document_id: str) -> list[DocumentChunk]:
        """Get all chunks for a document."""
        return [
            chunk for chunk in self._chunks.values()
            if chunk.document_id == document_id
        ]
    
    def get_chunks_by_patient(self, patient_id: str) -> list[DocumentChunk]:
        """Get all chunks for a patient."""
        return [
            chunk for chunk in self._chunks.values()
            if chunk.patient_id == patient_id
        ]
    
    @property
    def size(self) -> int:
        """Return the number of chunks in the store."""
        return len(self._chunks)
    
    def save(self):
        """Persist the vector store to disk."""
        if self._index is None:
            logger.warning("No index to save")
            return
        
        faiss = self._get_faiss()
        
        # Save FAISS index
        index_path = self.store_path / "index.faiss"
        faiss.write_index(self._index, str(index_path))
        
        # Save metadata
        metadata_path = self.store_path / "metadata.pkl"
        with open(metadata_path, "wb") as f:
            pickle.dump({
                "chunks": {k: v.model_dump() for k, v in self._chunks.items()},
                "id_map": self._id_map,
            }, f)
        
        logger.info(f"Saved vector store to {self.store_path}")
    
    def load(self) -> bool:
        """
        Load the vector store from disk.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        index_path = self.store_path / "index.faiss"
        metadata_path = self.store_path / "metadata.pkl"
        
        if not index_path.exists() or not metadata_path.exists():
            logger.info("No existing vector store found")
            return False
        
        try:
            faiss = self._get_faiss()
            
            # Load FAISS index
            self._index = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(metadata_path, "rb") as f:
                data = pickle.load(f)
            
            self._chunks = {
                k: DocumentChunk(**v) for k, v in data["chunks"].items()
            }
            self._id_map = data["id_map"]
            
            logger.info(f"Loaded vector store with {self.size} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False
    
    def clear(self):
        """Clear the vector store."""
        self._index = None
        self._chunks.clear()
        self._id_map.clear()
        logger.info("Vector store cleared")
    
    def _get_faiss(self):
        """Get the faiss module."""
        import faiss
        return faiss


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.load()  # Try to load existing store
    return _vector_store
