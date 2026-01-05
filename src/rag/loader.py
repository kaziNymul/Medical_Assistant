"""
Document loading and chunking for the RAG pipeline.

Handles:
- Loading documents from various sources (CSV, JSON, text)
- Chunking documents into appropriate sizes
- Applying PII masking before storage
"""

import csv
import json
import uuid
from pathlib import Path
from typing import Generator

from src.models.schemas import ClinicalDocument, DocumentChunk, SourceType
from src.utils.masking import get_masker, MaskingResult


class DocumentLoader:
    """
    Load clinical documents from various sources.
    """
    
    def __init__(self):
        self.masker = get_masker()
    
    def load_from_csv(
        self,
        file_path: Path,
        content_column: str = "text",
        patient_id_column: str = "patient_id",
        source_type_column: str | None = None,
        date_column: str | None = None,
    ) -> Generator[ClinicalDocument, None, None]:
        """
        Load documents from a CSV file.
        
        Args:
            file_path: Path to the CSV file.
            content_column: Column containing the document text.
            patient_id_column: Column containing patient ID.
            source_type_column: Optional column for source type.
            date_column: Optional column for document date.
            
        Yields:
            ClinicalDocument instances.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                content = row.get(content_column, "")
                if not content:
                    continue
                
                # Get patient ID and pseudonymize
                raw_patient_id = row.get(patient_id_column, str(uuid.uuid4()))
                patient_id = self.masker.pseudonymize_id(raw_patient_id)
                
                # Determine source type
                source_type = SourceType.UNKNOWN
                if source_type_column and source_type_column in row:
                    try:
                        source_type = SourceType(row[source_type_column].lower())
                    except ValueError:
                        source_type = SourceType.UNKNOWN
                
                # Get date if available
                doc_date = None
                if date_column and date_column in row:
                    doc_date = row[date_column]
                
                # Mask the content
                mask_result = self.masker.mask_text(content)
                
                yield ClinicalDocument(
                    document_id=self.masker.generate_document_id(),
                    patient_id=patient_id,
                    source_type=source_type,
                    content=mask_result.masked_text,
                    date=doc_date,
                    is_masked=mask_result.pii_detected,
                    metadata={
                        "items_masked": mask_result.items_masked,
                        "original_file": str(file_path.name),
                    }
                )
    
    def load_from_json(
        self,
        file_path: Path,
    ) -> Generator[ClinicalDocument, None, None]:
        """
        Load documents from a JSON or JSONL file.
        
        Expected format:
        - JSON: List of objects with 'content', 'patient_id', etc.
        - JSONL: One JSON object per line
        
        Args:
            file_path: Path to the JSON/JSONL file.
            
        Yields:
            ClinicalDocument instances.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            # Try to determine format
            first_char = f.read(1)
            f.seek(0)
            
            if first_char == "[":
                # Standard JSON array
                data = json.load(f)
            else:
                # JSONL format
                data = [json.loads(line) for line in f if line.strip()]
        
        for item in data:
            content = item.get("content", item.get("text", ""))
            if not content:
                continue
            
            # Pseudonymize patient ID
            raw_patient_id = item.get("patient_id", str(uuid.uuid4()))
            patient_id = self.masker.pseudonymize_id(raw_patient_id)
            
            # Mask content
            mask_result = self.masker.mask_text(content)
            
            # Get source type
            source_type = SourceType.UNKNOWN
            if "source_type" in item:
                try:
                    source_type = SourceType(item["source_type"].lower())
                except ValueError:
                    pass
            
            yield ClinicalDocument(
                document_id=self.masker.generate_document_id(),
                patient_id=patient_id,
                episode_id=item.get("episode_id"),
                source_type=source_type,
                content=mask_result.masked_text,
                date=item.get("date"),
                is_masked=mask_result.pii_detected,
                metadata={
                    "items_masked": mask_result.items_masked,
                    **item.get("metadata", {})
                }
            )
    
    def load_from_text(
        self,
        text: str,
        patient_id: str,
        source_type: SourceType = SourceType.UNKNOWN,
        document_date: str | None = None,
    ) -> ClinicalDocument:
        """
        Load a single document from text.
        
        Args:
            text: The document text.
            patient_id: Patient identifier (will be pseudonymized).
            source_type: Type of clinical document.
            document_date: Date of the document.
            
        Returns:
            ClinicalDocument instance.
        """
        # Pseudonymize and mask
        pseudo_patient_id = self.masker.pseudonymize_id(patient_id)
        mask_result = self.masker.mask_text(text)
        
        return ClinicalDocument(
            document_id=self.masker.generate_document_id(),
            patient_id=pseudo_patient_id,
            source_type=source_type,
            content=mask_result.masked_text,
            date=document_date,
            is_masked=mask_result.pii_detected,
            metadata={"items_masked": mask_result.items_masked}
        )


class DocumentChunker:
    """
    Chunk documents into smaller pieces for RAG.
    
    Uses overlapping chunks to preserve context across boundaries.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target size of each chunk in characters.
            chunk_overlap: Number of overlapping characters between chunks.
            min_chunk_size: Minimum chunk size (smaller chunks are merged).
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.masker = get_masker()
    
    def chunk_document(
        self,
        document: ClinicalDocument,
    ) -> list[DocumentChunk]:
        """
        Split a document into chunks.
        
        Args:
            document: The document to chunk.
            
        Returns:
            List of DocumentChunk instances.
        """
        text = document.content
        
        if len(text) <= self.chunk_size:
            # Document is small enough to be a single chunk
            return [
                DocumentChunk(
                    chunk_id=self.masker.generate_chunk_id(document.document_id, 0),
                    document_id=document.document_id,
                    patient_id=document.patient_id,
                    content=text,
                    source_type=document.source_type,
                    chunk_index=0,
                    total_chunks=1,
                    metadata=document.metadata,
                )
            ]
        
        # Split into chunks with overlap
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Find end position
            end = start + self.chunk_size
            
            if end >= len(text):
                # Last chunk
                chunk_text = text[start:]
            else:
                # Try to break at a sentence or paragraph boundary
                chunk_text = text[start:end]
                
                # Look for sentence boundary near the end
                for sep in ["\n\n", "\n", ". ", "? ", "! "]:
                    last_sep = chunk_text.rfind(sep)
                    if last_sep > self.chunk_size // 2:
                        chunk_text = chunk_text[:last_sep + len(sep)]
                        break
            
            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunks.append(chunk_text)
                chunk_index += 1
            
            # Move start position (with overlap)
            start += len(chunk_text) - self.chunk_overlap
            if start <= 0 and chunk_index > 0:
                break  # Prevent infinite loop
        
        # Create DocumentChunk instances
        total_chunks = len(chunks)
        return [
            DocumentChunk(
                chunk_id=self.masker.generate_chunk_id(document.document_id, i),
                document_id=document.document_id,
                patient_id=document.patient_id,
                content=chunk_text,
                source_type=document.source_type,
                chunk_index=i,
                total_chunks=total_chunks,
                metadata=document.metadata,
            )
            for i, chunk_text in enumerate(chunks)
        ]
    
    def chunk_documents(
        self,
        documents: list[ClinicalDocument],
    ) -> list[DocumentChunk]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of documents to chunk.
            
        Returns:
            List of all chunks from all documents.
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
        return all_chunks
