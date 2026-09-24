"""Memory retrieval tool (Phase 13).

Real embedding / pgvector memory search with semantic similarity and metadata filtering.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.engine.memory.retrieval import MemoryContext, MemoryRetrievalService
from app.engine.tools.base import BaseTool
from app.models.memory import MemoryType


class RetrieveMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=5, ge=1, le=50)
    workspace_id: str = Field(min_length=1, max_length=64)
    experiment_id: Optional[str] = Field(default=None, max_length=64)
    task_type: str = Field(default="classification", max_length=100)
    context_type: str = Field(default="experiment_planning", max_length=50)
    preferred_memory_types: Optional[List[str]] = Field(default=None)
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0)
    ranking_strategy: str = Field(default="composite", max_length=50)


class StoreMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    experiment_id: Optional[str] = Field(default=None, max_length=64)
    memory_type: str = Field(max_length=50)
    task_type: str = Field(max_length=100)
    dataset_fingerprint: Dict[str, Any]
    solution_strategy: str = Field(min_length=1, max_length=2000)
    achieved_metric_value: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metric_name: Optional[str] = Field(default=None, max_length=100)
    memory_metadata: Optional[Dict[str, Any]] = Field(default=None)
    success: bool = True


class RetrieveMemoryTool(BaseTool):
    name = "retrieve_memory"
    description = "Retrieve relevant experience memories using semantic similarity search."
    input_model = RetrieveMemoryInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        import asyncio
        assert isinstance(params, RetrieveMemoryInput)

        from app.db.session import AsyncSessionLocal
        from sqlalchemy.ext.asyncio import AsyncSession

        async def _retrieve() -> Dict[str, Any]:
            async with AsyncSessionLocal() as session:
                service = MemoryRetrievalService(session)

                preferred_types = None
                if params.preferred_memory_types:
                    preferred_types = [MemoryType(t) for t in params.preferred_memory_types]

                context = MemoryContext(
                    task_type=params.task_type,
                    dataset_fingerprint={"name": params.query},
                    workspace_id=uuid.UUID(params.workspace_id),
                    experiment_id=uuid.UUID(params.experiment_id) if params.experiment_id else None,
                    context_type=params.context_type,
                    preferred_memory_types=preferred_types,
                    min_similarity=params.min_similarity,
                    max_results=params.limit,
                    ranking_strategy=params.ranking_strategy,
                )

                result = await service.retrieve_relevant_experiences(context)

                return {
                    "query": params.query,
                    "entries": [
                        {
                            "id": str(rm.memory.id),
                            "memory_type": rm.memory.memory_type,
                            "task_type": rm.memory.task_type,
                            "solution_strategy": rm.memory.solution_strategy,
                            "achieved_metric_value": rm.memory.achieved_metric_value,
                            "metric_name": rm.memory.metric_name,
                            "similarity_score": rm.similarity_score,
                            "ranking_score": rm.ranking_score,
                            "rank_factors": rm.rank_factors,
                            "created_at": rm.memory.created_at.isoformat() if rm.memory.created_at else None,
                        }
                        for rm in result.memories
                    ],
                    "total": result.total_candidates,
                    "retrieval_time_ms": result.retrieval_time_ms,
                    "strategy_used": result.strategy_used,
                }

        return asyncio.run(_retrieve())


class StoreMemoryTool(BaseTool):
    name = "store_memory"
    description = "Store an experience memory (verified claim, experiment outcome, insight, etc.)."
    input_model = StoreMemoryInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        import asyncio
        assert isinstance(params, StoreMemoryInput)

        from app.db.session import AsyncSessionLocal
        from sqlalchemy.ext.asyncio import AsyncSession

        async def _store() -> Dict[str, Any]:
            async with AsyncSessionLocal() as session:
                service = MemoryRetrievalService(session)

                memory_type = MemoryType(params.memory_type)

                context = MemoryContext(
                    task_type=params.task_type,
                    dataset_fingerprint=params.dataset_fingerprint,
                    workspace_id=uuid.UUID(params.workspace_id),
                    experiment_id=uuid.UUID(params.experiment_id) if params.experiment_id else None,
                )

                memory = await service.store_experience(
                    context=context,
                    memory_type=memory_type,
                    solution_strategy=params.solution_strategy,
                    achieved_metric_value=params.achieved_metric_value,
                    metric_name=params.metric_name,
                    memory_metadata=params.memory_metadata,
                    success=params.success,
                )

                return {
                    "memory_id": str(memory.id),
                    "memory_type": memory.memory_type,
                    "status": memory.status,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None,
                }

        return asyncio.run(_store())
