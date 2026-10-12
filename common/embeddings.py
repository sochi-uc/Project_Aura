"""
common/embeddings.py — Pluggable Vector Embedding Abstraction

Design Rationale:
- Resource Efficiency: Loading neural embedding weights (PyTorch + HuggingFace) incurs
  a heavy memory (~500MB+) and latency footprint. We defer model initialization until
  the first vector computation is explicitly requested (`_ensure_model`).
- SQL Decoupling: PostgreSQL with pgvector expects vectors in the literal format
  `[0.123, 0.456, ...]::vector`. Formatting logic is centralized in `to_vector_sql`
  to keep database interaction consistent across the codebase.
- Testing Agility: `MockEmbeddingProvider` generates deterministic vectors instantaneously,
  allowing the unit test suite and CI pipelines to execute in milliseconds without
  downloading model weights or requiring a GPU.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from common.config import get_config

logger = logging.getLogger("AuraEmbeddings")


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface for text embedding providers.
    Decouples callers from sentence-transformers or any specific model runtime.
    """

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generate a dense semantic embedding vector for a single text string."""
        pass

    @abstractmethod
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a batch of text strings efficiently."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """The dimensionality of the output embedding vectors (e.g. 384)."""
        pass

    def to_vector_sql(self, vector: List[float]) -> str:
        """
        Formats a Python float list into a PostgreSQL pgvector string literal: '[x,y,z]'.
        Used directly in parameterized SQL queries targeting pgvector columns.
        """
        return f"[{','.join(map(str, vector))}]"


class SentenceTransformerProvider(BaseEmbeddingProvider):
    """
    Local embedding provider backed by the sentence-transformers library.
    Loads the underlying PyTorch model lazily on first access to conserve RAM.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384  # Standard dimensionality for all-MiniLM-L6-v2

    def _ensure_model(self):
        """
        Lazy-loader for the SentenceTransformer model.
        Defers heavy PyTorch and HuggingFace weight loading until actually needed.
        """
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}' (CPU/GPU)...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            
            # Smoothly handle sentence-transformers v2 vs v3 API rename
            if hasattr(self._model, "get_embedding_dimension"):
                self._dimension = self._model.get_embedding_dimension()
            elif hasattr(self._model, "get_sentence_embedding_dimension"):
                self._dimension = self._model.get_sentence_embedding_dimension()
            else:
                self._dimension = 384
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def get_embedding(self, text: str) -> List[float]:
        model = self._ensure_model()
        vector = model.encode([text])[0]
        return vector.tolist()

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        vectors = model.encode(texts)
        return [v.tolist() for v in vectors]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock provider for unit tests and resource-constrained environments.
    Produces repeatable 384-dimensional vectors via md5 hashing without PyTorch.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def get_embedding(self, text: str) -> List[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode('utf-8')).hexdigest()[:8], 16)
        return [float((seed + i) % 100) / 100.0 for i in range(self._dimension)]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.get_embedding(t) for t in texts]


# Provider cache to enforce singleton reuse per model configuration
_provider_instances = {}


def get_embedding_provider(
    name: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseEmbeddingProvider:
    """
    Factory resolving the appropriate embedding provider.
    Defaults to the provider defined in application settings.
    """
    cfg = get_config()
    provider_name = (name or cfg.embedding_provider).lower()
    target_model = model_name or cfg.embedding_model

    key = (provider_name, target_model)
    if key in _provider_instances:
        return _provider_instances[key]

    if provider_name in ("sentence_transformers", "local", "st"):
        provider = SentenceTransformerProvider(model_name=target_model)
    elif provider_name in ("mock", "test"):
        provider = MockEmbeddingProvider()
    else:
        logger.warning(
            f"Unknown embedding provider '{provider_name}'. Falling back to SentenceTransformer."
        )
        provider = SentenceTransformerProvider(model_name=target_model)

    _provider_instances[key] = provider
    return provider


def get_embedding(text: str) -> List[float]:
    """Convenience helper to compute a single embedding using the active provider."""
    return get_embedding_provider().get_embedding(text)


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Convenience helper to compute batch embeddings using the active provider."""
    return get_embedding_provider().get_embeddings_batch(texts)


def format_vector(vector: List[float]) -> str:
    """Convenience helper formatting a float list into a pgvector string representation: '[x,y,z]'."""
    return f"[{','.join(map(str, vector))}]"
