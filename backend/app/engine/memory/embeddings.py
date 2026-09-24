"""Embedding generation interface for memory system."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("autosage.memory.embeddings")


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding provider (OpenRouter, Groq, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        dimension: int = 1536,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=30.0,
            )
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = await self._get_client()
        response = await client.post(
            "/embeddings",
            json={"model": self._model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    async def embed_single(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace Inference API embedding provider."""

    def __init__(
        self,
        api_token: str,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        dimension: int = 384,
    ):
        self._api_token = api_token
        self._model = model
        self._dimension = dimension
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api-inference.huggingface.co",
                headers={"Authorization": f"Bearer {self._api_token}"},
                timeout=60.0,
            )
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = await self._get_client()
        response = await client.post(
            f"/models/{self._model}",
            json={"inputs": texts, "options": {"wait_for_model": True}},
        )
        response.raise_for_status()
        embeddings = response.json()
        if isinstance(embeddings[0], list):
            return embeddings
        return [embeddings]

    async def embed_single(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for testing/local development.

    Uses a simple hash-based approach to generate consistent embeddings
    without external API calls. Not suitable for production semantic search.
    """

    def __init__(self, dimension: int = 1536, seed: int = 42):
        self._dimension = dimension
        self._seed = seed

    def _hash_text(self, text: str) -> List[float]:
        import hashlib
        import random

        hash_obj = hashlib.md5(f"{self._seed}:{text}".encode())
        hash_bytes = hash_obj.digest()
        random.seed(int.from_bytes(hash_bytes[:4], "big"))
        return [random.uniform(-1, 1) for _ in range(self._dimension)]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_text(text) for text in texts]

    async def embed_single(self, text: str) -> List[float]:
        return self._hash_text(text)

    @property
    def model_name(self) -> str:
        return "deterministic-hash"

    @property
    def dimension(self) -> int:
        return self._dimension


class EmbeddingService:
    """High-level embedding service with provider fallback."""

    def __init__(self):
        self._provider: Optional[EmbeddingProvider] = None
        self._providers: List[EmbeddingProvider] = []

    def initialize(self) -> None:
        """Initialize providers based on configuration."""
        self._providers = []

        if settings.OPENAI_API_KEY:
            self._providers.append(
                OpenAIEmbeddingProvider(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
                    model=settings.OPENAI_EMBEDDING_MODEL or "text-embedding-3-small",
                    dimension=1536,
                )
            )

        if settings.OPENROUTER_API_KEY:
            self._providers.append(
                OpenAIEmbeddingProvider(
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url=settings.OPENROUTER_BASE_URL,
                    model=settings.OPENROUTER_EMBEDDING_MODEL or "openai/text-embedding-3-small",
                    dimension=1536,
                )
            )

        if settings.GROQ_API_KEY:
            self._providers.append(
                OpenAIEmbeddingProvider(
                    api_key=settings.GROQ_API_KEY,
                    base_url=settings.GROQ_BASE_URL,
                    model=settings.GROQ_EMBEDDING_MODEL or "text-embedding-3-small",
                    dimension=1536,
                )
            )

        if settings.HUGGINGFACE_API_TOKEN:
            self._providers.append(
                HuggingFaceEmbeddingProvider(
                    api_token=settings.HUGGINGFACE_API_TOKEN,
                    model=settings.HUGGINGFACE_EMBEDDING_MODEL or "sentence-transformers/all-MiniLM-L6-v2",
                    dimension=384,
                )
            )

        if not self._providers:
            logger.warning("No embedding providers configured; using deterministic fallback")
            self._providers.append(DeterministicEmbeddingProvider(dimension=1536))

        self._provider = self._providers[0]
        logger.info(f"Embedding service initialized with provider: {self._provider.model_name}")

    @property
    def provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self.initialize()
        assert self._provider is not None
        return self._provider

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with automatic fallback."""
        last_error = None
        for provider in self._providers:
            try:
                return await provider.embed(texts)
            except Exception as e:
                last_error = e
                logger.warning(f"Embedding provider {provider.model_name} failed: {e}")
        raise last_error or RuntimeError("No embedding providers available")

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text with automatic fallback."""
        last_error = None
        for provider in self._providers:
            try:
                return await provider.embed_single(text)
            except Exception as e:
                last_error = e
                logger.warning(f"Embedding provider {provider.model_name} failed: {e}")
        raise last_error or RuntimeError("No embedding providers available")

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    async def close(self) -> None:
        for provider in self._providers:
            if hasattr(provider, "close"):
                await provider.close()


embedding_service = EmbeddingService()