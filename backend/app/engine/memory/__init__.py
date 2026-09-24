"""Experience Memory Engine (Phase 13).

Provides vector-backed storage and retrieval of verified experiences,
experiment outcomes, dataset insights, and agent decisions.
"""

from app.engine.memory.embeddings import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
    DeterministicEmbeddingProvider,
    EmbeddingService,
    embedding_service,
)
from app.engine.memory.ranking import (
    RankingStrategy,
    SimilarityOnlyRanking,
    RecencyWeightedRanking,
    PerformanceWeightedRanking,
    AccessFrequencyRanking,
    CompositeRanking,
    RankedMemory,
    get_ranking_strategy,
)
from app.engine.memory.retrieval import (
    MemoryContext,
    MemoryRetrievalResult,
    MemoryRetrievalService,
    get_memory_retrieval_service,
)
from app.engine.memory.storage import MemoryStorageService

__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "EmbeddingService",
    "embedding_service",
    "RankingStrategy",
    "SimilarityOnlyRanking",
    "RecencyWeightedRanking",
    "PerformanceWeightedRanking",
    "AccessFrequencyRanking",
    "CompositeRanking",
    "RankedMemory",
    "get_ranking_strategy",
    "MemoryContext",
    "MemoryRetrievalResult",
    "MemoryRetrievalService",
    "get_memory_retrieval_service",
    "MemoryStorageService",
]