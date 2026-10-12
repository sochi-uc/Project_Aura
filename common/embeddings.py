import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from common.config import get_config

logger = logging.getLogger("AuraEmbeddings")


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface for text embedding providers.
    Decouples callers from sentence-transformers or any specific model library.
    """

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generate a single embedding vector for the provided text."""
        pass

    @abstractmethod
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate a batch of embedding vectors for the provided texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass

    def to_vector_sql(self, vector: List[float]) -> str:
        """
        Format a float list into a pgvector string representation: [x,y,z].
        """
        return f"[{','.join(map(str, vector))}]"


class SentenceTransformerProvider(BaseEmbeddingProvider):
    """
    Local embedding provider backed by sentence-transformers.
    Loads the underlying PyTorch model lazily on first access.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384  # Default for all-MiniLM-L6-v2

    def _ensure_model(self):
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}' (CPU/GPU)...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
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
    Deterministic mock embedding provider for tests and environments without PyTorch.
    Produces a 384-dimensional vector based on simple hash.
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


_provider_instances = {}


def get_embedding_provider(
    name: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseEmbeddingProvider:
    """
    Factory to retrieve or instantiate an embedding provider based on configuration.
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
    """Convenience function using the default configured embedding provider."""
    return get_embedding_provider().get_embedding(text)


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Convenience function using the default configured embedding provider."""
    return get_embedding_provider().get_embeddings_batch(texts)


def format_vector(vector: List[float]) -> str:
    """Format a python float list into a pgvector string representation: [x,y,z]."""
    return f"[{','.join(map(str, vector))}]"
