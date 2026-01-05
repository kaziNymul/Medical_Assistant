"""
RAG Pipeline orchestration.

Combines document loading, chunking, embedding, and retrieval
into a unified pipeline.
"""

from pathlib import Path
from typing import Optional

from src.models.schemas import ClinicalDocument, DocumentChunk, SourceType
from src.rag.loader import DocumentLoader, DocumentChunker
from src.rag.vector_store import VectorStore, get_vector_store
from src.utils.logging import logger


class RAGPipeline:
    """
    End-to-end RAG pipeline for clinical documents.
    
    Handles:
    - Document ingestion (with masking)
    - Chunking
    - Embedding and indexing
    - Retrieval
    """
    
    def __init__(
        self,
        vector_store: VectorStore | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Initialize the RAG pipeline.
        
        Args:
            vector_store: Vector store instance to use.
            chunk_size: Size of document chunks.
            chunk_overlap: Overlap between chunks.
        """
        self.vector_store = vector_store or get_vector_store()
        self.loader = DocumentLoader()
        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    def ingest_csv(
        self,
        file_path: str | Path,
        content_column: str = "text",
        patient_id_column: str = "patient_id",
        source_type_column: str | None = None,
        date_column: str | None = None,
    ) -> int:
        """
        Ingest documents from a CSV file.
        
        Args:
            file_path: Path to the CSV file.
            content_column: Column containing document text.
            patient_id_column: Column containing patient ID.
            source_type_column: Optional column for source type.
            date_column: Optional column for document date.
            
        Returns:
            Number of chunks created.
        """
        file_path = Path(file_path)
        logger.info(f"Ingesting documents from {file_path}")
        
        # Load documents
        documents = list(self.loader.load_from_csv(
            file_path,
            content_column=content_column,
            patient_id_column=patient_id_column,
            source_type_column=source_type_column,
            date_column=date_column,
        ))
        
        logger.info(f"Loaded {len(documents)} documents")
        
        # Chunk documents
        all_chunks = self.chunker.chunk_documents(documents)
        logger.info(f"Created {len(all_chunks)} chunks")
        
        # Add to vector store
        self.vector_store.add_chunks(all_chunks)
        
        # Persist
        self.vector_store.save()
        
        return len(all_chunks)
    
    def ingest_json(self, file_path: str | Path) -> int:
        """
        Ingest documents from a JSON/JSONL file.
        
        Args:
            file_path: Path to the JSON file.
            
        Returns:
            Number of chunks created.
        """
        file_path = Path(file_path)
        logger.info(f"Ingesting documents from {file_path}")
        
        documents = list(self.loader.load_from_json(file_path))
        logger.info(f"Loaded {len(documents)} documents")
        
        all_chunks = self.chunker.chunk_documents(documents)
        logger.info(f"Created {len(all_chunks)} chunks")
        
        self.vector_store.add_chunks(all_chunks)
        self.vector_store.save()
        
        return len(all_chunks)
    
    def ingest_gold_json(self, file_path: str | Path) -> int:
        """
        Ingest AI-ready Gold layer JSON files.
        
        These files have a specific structure with 'documents' array
        containing pre-processed, masked text ready for RAG.
        
        Args:
            file_path: Path to the Gold layer JSON file.
            
        Returns:
            Number of chunks created.
        """
        import json
        
        file_path = Path(file_path)
        logger.info(f"Ingesting Gold layer data from {file_path}")
        
        with open(file_path) as f:
            data = json.load(f)
        
        documents = data.get("documents", [])
        
        if not documents:
            logger.warning(f"No documents found in {file_path}")
            return 0
        
        # Convert to ClinicalDocument objects
        clinical_docs = []
        for doc in documents:
            text = doc.get("text", "")
            if not text or len(text.strip()) < 10:
                continue
            
            clinical_doc = ClinicalDocument(
                document_id=doc.get("id", ""),
                content=text,
                masked_content=text,  # Already masked in Gold layer
                patient_id=doc.get("id", "")[:8],  # Use part of ID as patient
                source_type=SourceType.UNKNOWN,
                document_date=data.get("created_at"),
                metadata=doc.get("metadata", {}),
            )
            clinical_docs.append(clinical_doc)
        
        logger.info(f"Loaded {len(clinical_docs)} documents from Gold layer")
        
        # Chunk and add to vector store
        all_chunks = self.chunker.chunk_documents(clinical_docs)
        logger.info(f"Created {len(all_chunks)} chunks")
        
        self.vector_store.add_chunks(all_chunks)
        self.vector_store.save()
        
        return len(all_chunks)
    
    def ingest_document(
        self,
        text: str,
        patient_id: str,
        source_type: SourceType = SourceType.UNKNOWN,
        document_date: str | None = None,
    ) -> tuple[str, int]:
        """
        Ingest a single document.
        
        Args:
            text: Document text.
            patient_id: Patient identifier.
            source_type: Type of clinical document.
            document_date: Date of the document.
            
        Returns:
            Tuple of (document_id, number of chunks).
        """
        # Load and mask
        document = self.loader.load_from_text(
            text=text,
            patient_id=patient_id,
            source_type=source_type,
            document_date=document_date,
        )
        
        # Chunk
        chunks = self.chunker.chunk_document(document)
        
        # Add to vector store
        self.vector_store.add_chunks(chunks)
        self.vector_store.save()
        
        logger.info(f"Ingested document {document.document_id} with {len(chunks)} chunks")
        
        return document.document_id, len(chunks)
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        patient_id: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Retrieve relevant document chunks.
        
        Args:
            query: Query text.
            top_k: Number of results.
            patient_id: Optional patient filter.
            
        Returns:
            List of (chunk, score) tuples.
        """
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            patient_id=patient_id,
        )
        
        logger.info(f"Retrieved {len(results)} chunks for query")
        return results
    
    def get_context(
        self,
        query: str,
        top_k: int = 5,
        patient_id: str | None = None,
        separator: str = "\n\n---\n\n",
    ) -> tuple[str, list[DocumentChunk]]:
        """
        Get combined context for a query.
        
        Args:
            query: Query text.
            top_k: Number of chunks to retrieve.
            patient_id: Optional patient filter.
            separator: Separator between chunks.
            
        Returns:
            Tuple of (combined context text, list of chunks).
        """
        results = self.retrieve(query, top_k=top_k, patient_id=patient_id)
        
        if not results:
            return "", []
        
        chunks = [r[0] for r in results]
        context = separator.join(chunk.content for chunk in chunks)
        
        return context, chunks
    
    @property
    def document_count(self) -> int:
        """Get the number of unique documents."""
        return len(set(
            chunk.document_id for chunk in self.vector_store._chunks.values()
        ))
    
    @property
    def chunk_count(self) -> int:
        """Get the total number of chunks."""
        return self.vector_store.size


# Global pipeline instance
_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create the global RAG pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
