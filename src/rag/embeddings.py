"""
Embeddings generation for the RAG pipeline.

Supports:
- Local embeddings via Sentence-Transformers (Phase 1)
- AWS Bedrock embeddings (Phase 2)
"""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from config.settings import settings
from src.utils.logging import logger


class BaseEmbeddings(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class SentenceTransformerEmbeddings(BaseEmbeddings):
    """
    Local embeddings using Sentence-Transformers.
    
    Used in Phase 1 for local development.
    """
    
    def __init__(self, model_name: str | None = None):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Name of the sentence-transformer model.
        """
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._dimension: int | None = None
        
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded. Dimension: {self._dimension}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector as numpy array.
        """
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)
    
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            Matrix of embeddings (n_texts x dimension).
        """
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.astype(np.float32)
    
    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        self._load_model()
        return self._dimension


class BedrockEmbeddings(BaseEmbeddings):
    """
    AWS Bedrock embeddings.
    
    Used in Phase 2 for cloud deployment.
    Supports Titan and Cohere embedding models.
    """
    
    # Embedding dimensions for different models
    MODEL_DIMENSIONS = {
        "amazon.titan-embed-text-v2:0": 1024,
        "amazon.titan-embed-text-v1": 1536,
        "cohere.embed-english-v3": 1024,
        "cohere.embed-multilingual-v3": 1024,
    }
    
    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
    ):
        """
        Initialize Bedrock embeddings.
        
        Args:
            model_id: Bedrock model ID for embeddings.
            region: AWS region.
        """
        self.model_id = model_id or settings.bedrock_embedding_model
        self.region = region or settings.aws_region
        self._client = None
    
    def _get_client(self):
        """Get or create the Bedrock client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region,
                )
                logger.info(f"Bedrock client initialized for {self.model_id}")
            except ImportError:
                raise ImportError(
                    "boto3 is required for Bedrock. "
                    "Install with: pip install boto3"
                )
        return self._client
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding using Bedrock.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector as numpy array.
        """
        import json
        
        client = self._get_client()
        
        # Prepare request based on model type
        if "titan" in self.model_id.lower():
            body = json.dumps({"inputText": text})
        elif "cohere" in self.model_id.lower():
            body = json.dumps({
                "texts": [text],
                "input_type": "search_document",
            })
        else:
            body = json.dumps({"inputText": text})
        
        response = client.invoke_model(
            modelId=self.model_id,
            body=body,
        )
        
        response_body = json.loads(response["body"].read())
        
        # Extract embedding based on model type
        if "titan" in self.model_id.lower():
            embedding = response_body["embedding"]
        elif "cohere" in self.model_id.lower():
            embedding = response_body["embeddings"][0]
        else:
            embedding = response_body.get("embedding", response_body.get("embeddings", [[]])[0])
        
        return np.array(embedding, dtype=np.float32)
    
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Note: Bedrock has batch limits, so we process in batches.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            Matrix of embeddings.
        """
        embeddings = []
        batch_size = 25  # Bedrock batch limit
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            if "cohere" in self.model_id.lower():
                # Cohere supports batch embedding
                embeddings.extend(self._embed_batch_cohere(batch))
            else:
                # Process individually for Titan
                for text in batch:
                    embeddings.append(self.embed_text(text))
        
        return np.array(embeddings, dtype=np.float32)
    
    def _embed_batch_cohere(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch using Cohere."""
        import json
        
        client = self._get_client()
        body = json.dumps({
            "texts": texts,
            "input_type": "search_document",
        })
        
        response = client.invoke_model(
            modelId=self.model_id,
            body=body,
        )
        
        response_body = json.loads(response["body"].read())
        return [np.array(e, dtype=np.float32) for e in response_body["embeddings"]]
    
    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self.MODEL_DIMENSIONS.get(self.model_id, 1024)


def get_embeddings(provider: str | None = None) -> BaseEmbeddings:
    """
    Get the appropriate embeddings provider.
    
    Args:
        provider: Override the provider ('local' or 'bedrock').
        
    Returns:
        Embeddings instance.
    """
    import os
    
    provider = provider or settings.llm_provider
    
    # Check directly in environment (may be set after settings cache)
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if provider == "bedrock" and aws_key and aws_secret:
        logger.info("Using Bedrock embeddings (Titan)")
        return BedrockEmbeddings()
    else:
        logger.info("Using local sentence-transformer embeddings")
        return SentenceTransformerEmbeddings()
