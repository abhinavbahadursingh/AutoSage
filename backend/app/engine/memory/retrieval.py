"""Agent-facing memory retrieval interface (Phase 13).

High-level interface for agents to store and retrieve relevant experiences.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.memory.embeddings import embedding_service
from app.engine.memory.ranking import (
    CompositeRanking,
    RankedMemory,
    get_ranking_strategy,
)
from app.engine.memory.storage import MemoryStorageService
from app.models.memory import ExperienceMemory, MemoryStatus, MemoryType

logger = logging.getLogger("autosage.memory.retrieval")


@dataclass
class MemoryRetrievalResult:
    """Result of a memory retrieval operation."""
    memories: List[RankedMemory]
    query_embedding: List[float]
    total_candidates: int
    retrieval_time_ms: float
    strategy_used: str


@dataclass
class MemoryContext:
    """Context for memory retrieval, built from agent state."""
    task_type: str
    dataset_fingerprint: Dict[str, Any]
    workspace_id: uuid.UUID
    experiment_id: Optional[uuid.UUID] = None
    current_strategy: Optional[str] = None
    target_metric: Optional[str] = None
    context_type: str = "experiment_planning"  # experiment_planning, debugging, dataset_analysis
    preferred_memory_types: Optional[List[MemoryType]] = None
    min_similarity: float = 0.3
    max_results: int = 10
    ranking_strategy: str = "composite"


class MemoryRetrievalService:
    """High-level service for agent memory operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.storage = MemoryStorageService(session)
        self._ranking_strategy = CompositeRanking()

    async def retrieve_relevant_experiences(
        self,
        context: MemoryContext,
    ) -> MemoryRetrievalResult:
        """Retrieve relevant experiences for the given context."""
        import time
        start_time = time.perf_counter()

        query_text = self._build_query_text(context)
        query_embedding = await embedding_service.embed_single(query_text)

        candidate_memories = await self.storage.retrieve_similar(
            query_embedding=query_embedding,
            workspace_id=context.workspace_id,
            limit=context.max_results * 3,
            memory_types=context.preferred_memory_types,
            task_types=[context.task_type] if context.task_type else None,
            status=MemoryStatus.ACTIVE,
            min_similarity=context.min_similarity,
            dataset_fingerprint_filter=self._extract_fingerprint_filter(context),
        )

        query_context = {
            "context_type": context.context_type,
            "task_type": context.task_type,
            "target_metric": context.target_metric,
        }

        ranked = self._ranking_strategy.rank(candidate_memories, query_context)

        ranked = ranked[:context.max_results]

        for ranked_mem in ranked:
            await self.storage.update_access_stats(ranked_mem.memory.id, context.workspace_id)

        retrieval_time = (time.perf_counter() - start_time) * 1000

        return MemoryRetrievalResult(
            memories=ranked,
            query_embedding=query_embedding,
            total_candidates=len(candidate_memories),
            retrieval_time_ms=retrieval_time,
            strategy_used=type(self._ranking_strategy).__name__,
        )

    async def store_experience(
        self,
        context: MemoryContext,
        memory_type: MemoryType,
        solution_strategy: str,
        achieved_metric_value: Optional[float] = None,
        metric_name: Optional[str] = None,
        memory_metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> ExperienceMemory:
        """Store an experience memory based on the context."""
        if memory_type == MemoryType.SUCCESSFUL_EXPERIMENT or memory_type == MemoryType.FAILED_EXPERIMENT:
            return await self.storage.store_experiment_outcome(
                workspace_id=context.workspace_id,
                experiment_id=context.experiment_id or uuid.uuid4(),
                source_run_id=uuid.uuid4(),
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                solution_strategy=solution_strategy,
                metric_name=metric_name or context.target_metric or "accuracy",
                metric_value=achieved_metric_value or 0.0,
                success=success,
                memory_metadata=memory_metadata,
            )
        elif memory_type == MemoryType.VERIFIED_CLAIM:
            return await self.storage.store_verified_claim(
                workspace_id=context.workspace_id,
                claim=solution_strategy,
                evidence=memory_metadata or {},
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                experiment_id=context.experiment_id,
            )
        elif memory_type == MemoryType.DATASET_INSIGHT:
            return await self.storage.store_dataset_insight(
                workspace_id=context.workspace_id,
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                insight=solution_strategy,
                memory_metadata=memory_metadata,
                experiment_id=context.experiment_id,
            )
        elif memory_type == MemoryType.MODEL_SELECTION_EXPERIENCE:
            return await self.storage.store_model_selection_experience(
                workspace_id=context.workspace_id,
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                model_family=memory_metadata.get("model_family", "unknown"),
                hyperparameters=memory_metadata.get("hyperparameters", {}),
                metric_name=metric_name or context.target_metric or "accuracy",
                metric_value=achieved_metric_value or 0.0,
                success=success,
                memory_metadata=memory_metadata,
                experiment_id=context.experiment_id,
            )
        elif memory_type == MemoryType.PREPROCESSING_EXPERIENCE:
            return await self.storage.store_preprocessing_experience(
                workspace_id=context.workspace_id,
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                preprocessing_steps=memory_metadata.get("preprocessing_steps", []),
                metric_name=metric_name or context.target_metric or "accuracy",
                metric_value=achieved_metric_value or 0.0,
                success=success,
                memory_metadata=memory_metadata,
                experiment_id=context.experiment_id,
            )
        elif memory_type == MemoryType.AGENT_DECISION:
            return await self.storage.store_agent_decision(
                workspace_id=context.workspace_id,
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                agent_name=memory_metadata.get("agent_name", "unknown"),
                decision_type=memory_metadata.get("decision_type", "general"),
                rationale=solution_strategy,
                confidence=memory_metadata.get("confidence"),
                memory_metadata=memory_metadata,
                experiment_id=context.experiment_id,
            )
        else:
            return await self.storage.store_memory(
                workspace_id=context.workspace_id,
                memory_type=memory_type,
                task_type=context.task_type,
                dataset_fingerprint=context.dataset_fingerprint,
                solution_strategy=solution_strategy,
                memory_metadata=memory_metadata,
                experiment_id=context.experiment_id,
                achieved_metric_value=achieved_metric_value,
                metric_name=metric_name,
            )

    def _build_query_text(self, context: MemoryContext) -> str:
        """Build query text for embedding generation."""
        parts = [
            f"Task: {context.task_type}",
            f"Dataset: {context.dataset_fingerprint.get('name', 'unknown')}",
            f"Features: {context.dataset_fingerprint.get('n_features', 'unknown')}",
            f"Rows: {context.dataset_fingerprint.get('n_rows', 'unknown')}",
        ]
        if context.current_strategy:
            parts.append(f"Current approach: {context.current_strategy}")
        if context.target_metric:
            parts.append(f"Target metric: {context.target_metric}")
        return " | ".join(parts)

    def _extract_fingerprint_filter(self, context: MemoryContext) -> Optional[Dict[str, Any]]:
        """Extract key fingerprint fields for exact filtering."""
        filter_fields = {}
        for key in ["n_features", "n_rows", "target_type"]:
            if key in context.dataset_fingerprint:
                filter_fields[key] = context.dataset_fingerprint[key]
        return filter_fields if filter_fields else None

    async def get_memory_by_id(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Get a specific memory by ID."""
        return await self.storage.get_memory_by_id(memory_id, workspace_id)

    async def archive_memory(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Archive a memory."""
        return await self.storage.archive_memory(memory_id, workspace_id)

    async def get_workspace_stats(self, workspace_id: uuid.UUID) -> Dict[str, Any]:
        """Get memory statistics for a workspace."""
        return await self.storage.get_memory_stats(workspace_id)

    def set_ranking_strategy(self, strategy: str, **kwargs) -> None:
        """Set the ranking strategy for retrieval."""
        self._ranking_strategy = get_ranking_strategy(strategy, **kwargs)


async def get_memory_retrieval_service(session: AsyncSession) -> MemoryRetrievalService:
    """FastAPI dependency for memory retrieval service."""
    return MemoryRetrievalService(session)