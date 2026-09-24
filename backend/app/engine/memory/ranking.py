"""Memory ranking strategies for experience retrieval."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.models.memory import ExperienceMemory, MemoryType

logger = logging.getLogger("autosage.memory.ranking")


@dataclass
class RankedMemory:
    """A memory entry with its ranking score and metadata."""
    memory: ExperienceMemory
    similarity_score: float
    ranking_score: float
    rank_factors: Dict[str, float]


class RankingStrategy(ABC):
    """Abstract base class for memory ranking strategies."""

    @abstractmethod
    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        """Rank memories based on similarity and context."""
        pass


class SimilarityOnlyRanking(RankingStrategy):
    """Rank purely by vector similarity score."""

    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        return [
            RankedMemory(
                memory=mem,
                similarity_score=sim,
                ranking_score=sim,
                rank_factors={"similarity": sim},
            )
            for mem, sim in memories
        ]


class RecencyWeightedRanking(RankingStrategy):
    """Rank by similarity weighted by recency."""

    def __init__(self, recency_weight: float = 0.3, half_life_days: float = 30.0):
        self.recency_weight = recency_weight
        self.half_life_days = half_life_days

    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        import math
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        ranked = []

        for mem, sim in memories:
            age_days = (now - mem.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
            recency_factor = math.exp(-age_days / self.half_life_days)
            ranking_score = (1 - self.recency_weight) * sim + self.recency_weight * recency_factor

            ranked.append(
                RankedMemory(
                    memory=mem,
                    similarity_score=sim,
                    ranking_score=ranking_score,
                    rank_factors={
                        "similarity": sim,
                        "recency": recency_factor,
                        "age_days": age_days,
                    },
                )
            )

        ranked.sort(key=lambda x: x.ranking_score, reverse=True)
        return ranked


class PerformanceWeightedRanking(RankingStrategy):
    """Rank by similarity weighted by achieved metric performance."""

    def __init__(self, performance_weight: float = 0.4):
        self.performance_weight = performance_weight

    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        ranked = []

        for mem, sim in memories:
            performance_factor = 0.5
            if mem.achieved_metric_value is not None:
                performance_factor = min(max(mem.achieved_metric_value, 0.0), 1.0)

            ranking_score = (1 - self.performance_weight) * sim + self.performance_weight * performance_factor

            ranked.append(
                RankedMemory(
                    memory=mem,
                    similarity_score=sim,
                    ranking_score=ranking_score,
                    rank_factors={
                        "similarity": sim,
                        "performance": performance_factor,
                        "metric_value": mem.achieved_metric_value or 0.0,
                        "metric_name": mem.metric_name or "unknown",
                    },
                )
            )

        ranked.sort(key=lambda x: x.ranking_score, reverse=True)
        return ranked


class AccessFrequencyRanking(RankingStrategy):
    """Rank by similarity weighted by access frequency (popularity)."""

    def __init__(self, popularity_weight: float = 0.2, max_access_for_full_score: int = 100):
        self.popularity_weight = popularity_weight
        self.max_access = max_access_for_full_score

    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        ranked = []

        for mem, sim in memories:
            popularity_factor = min(mem.access_count / self.max_access, 1.0)
            ranking_score = (1 - self.popularity_weight) * sim + self.popularity_weight * popularity_factor

            ranked.append(
                RankedMemory(
                    memory=mem,
                    similarity_score=sim,
                    ranking_score=ranking_score,
                    rank_factors={
                        "similarity": sim,
                        "popularity": popularity_factor,
                        "access_count": mem.access_count,
                    },
                )
            )

        ranked.sort(key=lambda x: x.ranking_score, reverse=True)
        return ranked


class CompositeRanking(RankingStrategy):
    """Composite ranking combining multiple factors."""

    def __init__(
        self,
        similarity_weight: float = 0.4,
        recency_weight: float = 0.2,
        performance_weight: float = 0.2,
        popularity_weight: float = 0.1,
        type_relevance_weight: float = 0.1,
        half_life_days: float = 30.0,
        max_access: int = 100,
    ):
        self.similarity_weight = similarity_weight
        self.recency_weight = recency_weight
        self.performance_weight = performance_weight
        self.popularity_weight = popularity_weight
        self.type_relevance_weight = type_relevance_weight
        self.half_life_days = half_life_days
        self.max_access = max_access

        # Type relevance for different query contexts
        self.type_relevance = {
            "experiment_planning": {
                MemoryType.SUCCESSFUL_EXPERIMENT: 1.0,
                MemoryType.MODEL_SELECTION_EXPERIENCE: 0.9,
                MemoryType.PREPROCESSING_EXPERIENCE: 0.8,
                MemoryType.VERIFIED_CLAIM: 0.7,
                MemoryType.DATASET_INSIGHT: 0.6,
                MemoryType.AGENT_DECISION: 0.5,
                MemoryType.FAILED_EXPERIMENT: 0.3,
            },
            "debugging": {
                MemoryType.FAILED_EXPERIMENT: 1.0,
                MemoryType.AGENT_DECISION: 0.8,
                MemoryType.VERIFIED_CLAIM: 0.7,
                MemoryType.SUCCESSFUL_EXPERIMENT: 0.6,
                MemoryType.MODEL_SELECTION_EXPERIENCE: 0.5,
                MemoryType.PREPROCESSING_EXPERIENCE: 0.5,
                MemoryType.DATASET_INSIGHT: 0.4,
            },
            "dataset_analysis": {
                MemoryType.DATASET_INSIGHT: 1.0,
                MemoryType.VERIFIED_CLAIM: 0.8,
                MemoryType.SUCCESSFUL_EXPERIMENT: 0.6,
                MemoryType.FAILED_EXPERIMENT: 0.5,
                MemoryType.PREPROCESSING_EXPERIENCE: 0.5,
                MemoryType.MODEL_SELECTION_EXPERIENCE: 0.4,
                MemoryType.AGENT_DECISION: 0.3,
            },
        }

    def _get_type_relevance(self, memory: ExperienceMemory, query_context: Dict[str, Any]) -> float:
        context_type = query_context.get("context_type", "experiment_planning")
        relevance_map = self.type_relevance.get(context_type, self.type_relevance["experiment_planning"])
        mem_type = MemoryType(memory.memory_type) if memory.memory_type in MemoryType._value2member_map_ else None
        return relevance_map.get(mem_type, 0.5) if mem_type else 0.5

    def rank(
        self,
        memories: List[Tuple[ExperienceMemory, float]],
        query_context: Dict[str, Any],
    ) -> List[RankedMemory]:
        import math
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        ranked = []

        for mem, sim in memories:
            age_days = (now - mem.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
            recency_factor = math.exp(-age_days / self.half_life_days)

            performance_factor = 0.5
            if mem.achieved_metric_value is not None:
                performance_factor = min(max(mem.achieved_metric_value, 0.0), 1.0)

            popularity_factor = min(mem.access_count / self.max_access, 1.0)

            type_relevance = self._get_type_relevance(mem, query_context)

            ranking_score = (
                self.similarity_weight * sim
                + self.recency_weight * recency_factor
                + self.performance_weight * performance_factor
                + self.popularity_weight * popularity_factor
                + self.type_relevance_weight * type_relevance
            )

            ranked.append(
                RankedMemory(
                    memory=mem,
                    similarity_score=sim,
                    ranking_score=ranking_score,
                    rank_factors={
                        "similarity": sim,
                        "recency": recency_factor,
                        "age_days": age_days,
                        "performance": performance_factor,
                        "metric_value": mem.achieved_metric_value or 0.0,
                        "popularity": popularity_factor,
                        "access_count": mem.access_count,
                        "type_relevance": type_relevance,
                    },
                )
            )

        ranked.sort(key=lambda x: x.ranking_score, reverse=True)
        return ranked


def get_ranking_strategy(strategy: str, **kwargs) -> RankingStrategy:
    """Factory function to get a ranking strategy by name."""
    strategies = {
        "similarity": SimilarityOnlyRanking,
        "recency_weighted": RecencyWeightedRanking,
        "performance_weighted": PerformanceWeightedRanking,
        "access_frequency": AccessFrequencyRanking,
        "composite": CompositeRanking,
    }
    if strategy not in strategies:
        raise ValueError(f"Unknown ranking strategy: {strategy}")
    return strategies[strategy](**kwargs)