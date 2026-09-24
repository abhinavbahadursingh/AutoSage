"""Memory storage service for experience memory system."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.engine.memory.embeddings import embedding_service
from app.models.memory import ExperienceMemory, MemoryType, MemoryStatus

logger = logging.getLogger("autosage.memory.storage")


class MemoryStorageService:
    """Service for storing and retrieving experience memories."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_memory(
        self,
        workspace_id: uuid.UUID,
        memory_type: MemoryType,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        solution_strategy: str,
        memory_metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[uuid.UUID] = None,
        source_run_id: Optional[uuid.UUID] = None,
        achieved_metric_value: Optional[float] = None,
        metric_name: Optional[str] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        embedding: Optional[List[float]] = None,
        generate_embedding: bool = True,
    ) -> ExperienceMemory:
        """Store a new memory entry with optional embedding generation."""
        if embedding is None and generate_embedding:
            embed_text = self._build_embedding_text(
                task_type=task_type,
                dataset_fingerprint=dataset_fingerprint,
                solution_strategy=solution_strategy,
                memory_metadata=memory_metadata or {},
            )
            embedding = await embedding_service.embed_single(embed_text)

        memory = ExperienceMemory(
            workspace_id=workspace_id,
            experiment_id=experiment_id,
            source_run_id=source_run_id,
            memory_type=memory_type.value,
            status=status.value,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=solution_strategy,
            achieved_metric_value=achieved_metric_value,
            metric_name=metric_name,
            memory_metadata=memory_metadata or {},
            embedding=embedding,
            embedding_model=embedding_service.model_name if embedding else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        logger.info(f"Stored memory {memory.id} of type {memory_type.value}")
        return memory

    async def store_verified_claim(
        self,
        workspace_id: uuid.UUID,
        claim: str,
        evidence: Dict[str, Any],
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        experiment_id: Optional[uuid.UUID] = None,
        source_run_id: Optional[uuid.UUID] = None,
    ) -> ExperienceMemory:
        """Store a verified claim as a memory entry."""
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=MemoryType.VERIFIED_CLAIM,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=claim,
            memory_metadata={"evidence": evidence, "claim": claim},
            experiment_id=experiment_id,
            source_run_id=source_run_id,
            status=MemoryStatus.ACTIVE,
        )

    async def store_experiment_outcome(
        self,
        workspace_id: uuid.UUID,
        experiment_id: uuid.UUID,
        source_run_id: uuid.UUID,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        solution_strategy: str,
        metric_name: str,
        metric_value: float,
        success: bool,
        memory_metadata: Optional[Dict[str, Any]] = None,
    ) -> ExperienceMemory:
        """Store a successful or failed experiment outcome."""
        memory_type = (
            MemoryType.SUCCESSFUL_EXPERIMENT if success else MemoryType.FAILED_EXPERIMENT
        )
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=memory_type,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=solution_strategy,
            memory_metadata=memory_metadata or {},
            experiment_id=experiment_id,
            source_run_id=source_run_id,
            achieved_metric_value=metric_value,
            metric_name=metric_name,
            status=MemoryStatus.ACTIVE,
        )

    async def store_dataset_insight(
        self,
        workspace_id: uuid.UUID,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        insight: str,
        memory_metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> ExperienceMemory:
        """Store a dataset insight."""
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=MemoryType.DATASET_INSIGHT,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=insight,
            memory_metadata=memory_metadata or {},
            experiment_id=experiment_id,
            status=MemoryStatus.ACTIVE,
        )

    async def store_model_selection_experience(
        self,
        workspace_id: uuid.UUID,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        model_family: str,
        hyperparameters: Dict[str, Any],
        metric_name: str,
        metric_value: float,
        success: bool,
        memory_metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> ExperienceMemory:
        """Store a model selection experience."""
        strategy = f"Model: {model_family}, Params: {hyperparameters}"
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=MemoryType.MODEL_SELECTION_EXPERIENCE,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=strategy,
            memory_metadata={
                "model_family": model_family,
                "hyperparameters": hyperparameters,
                "success": success,
                **(memory_metadata or {}),
            },
            experiment_id=experiment_id,
            achieved_metric_value=metric_value,
            metric_name=metric_name,
            status=MemoryStatus.ACTIVE,
        )

    async def store_preprocessing_experience(
        self,
        workspace_id: uuid.UUID,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        preprocessing_steps: List[str],
        metric_name: str,
        metric_value: float,
        success: bool,
        memory_metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> ExperienceMemory:
        """Store a preprocessing experience."""
        strategy = " -> ".join(preprocessing_steps)
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=MemoryType.PREPROCESSING_EXPERIENCE,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=strategy,
            memory_metadata={
                "preprocessing_steps": preprocessing_steps,
                "success": success,
                **(memory_metadata or {}),
            },
            experiment_id=experiment_id,
            achieved_metric_value=metric_value,
            metric_name=metric_name,
            status=MemoryStatus.ACTIVE,
        )

    async def store_agent_decision(
        self,
        workspace_id: uuid.UUID,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        agent_name: str,
        decision_type: str,
        rationale: str,
        confidence: Optional[float] = None,
        memory_metadata: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> ExperienceMemory:
        """Store an agent decision as a memory entry."""
        return await self.store_memory(
            workspace_id=workspace_id,
            memory_type=MemoryType.AGENT_DECISION,
            task_type=task_type,
            dataset_fingerprint=dataset_fingerprint,
            solution_strategy=rationale,
            memory_metadata={
                "agent_name": agent_name,
                "decision_type": decision_type,
                "rationale": rationale,
                "confidence": confidence,
                **(memory_metadata or {}),
            },
            experiment_id=experiment_id,
            status=MemoryStatus.ACTIVE,
        )

    def _build_embedding_text(
        self,
        task_type: str,
        dataset_fingerprint: Dict[str, Any],
        solution_strategy: str,
        memory_metadata: Dict[str, Any],
    ) -> str:
        """Build text representation for embedding generation."""
        parts = [
            f"Task: {task_type}",
            f"Dataset: {dataset_fingerprint.get('name', 'unknown')}",
            f"Features: {dataset_fingerprint.get('n_features', 'unknown')}",
            f"Rows: {dataset_fingerprint.get('n_rows', 'unknown')}",
            f"Strategy: {solution_strategy}",
        ]
        if memory_metadata:
            parts.append(f"Metadata: {memory_metadata}")
        return " | ".join(parts)

    async def retrieve_similar(
        self,
        query_embedding: List[float],
        workspace_id: uuid.UUID,
        limit: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
        task_types: Optional[List[str]] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        min_similarity: float = 0.0,
        dataset_fingerprint_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[ExperienceMemory, float]]:
        """Retrieve similar memories using vector similarity with metadata filtering."""
        conditions = [
            ExperienceMemory.workspace_id == workspace_id,
            ExperienceMemory.status == status.value,
        ]

        if memory_types:
            conditions.append(ExperienceMemory.memory_type.in_([mt.value for mt in memory_types]))

        if task_types:
            conditions.append(ExperienceMemory.task_type.in_(task_types))

        if dataset_fingerprint_filter:
            for key, value in dataset_fingerprint_filter.items():
                conditions.append(ExperienceMemory.dataset_fingerprint[key].astext == str(value))

        query = (
            select(
                ExperienceMemory,
                (1 - ExperienceMemory.embedding.cosine_distance(query_embedding)).label("similarity"),
            )
            .where(and_(*conditions))
            .where(ExperienceMemory.embedding.is_not(None))
        )

        if min_similarity > 0:
            query = query.where(
                (1 - ExperienceMemory.embedding.cosine_distance(query_embedding)) >= min_similarity
            )

        query = query.order_by(text("similarity DESC")).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]

    async def retrieve_by_metadata(
        self,
        workspace_id: uuid.UUID,
        memory_types: Optional[List[MemoryType]] = None,
        task_types: Optional[List[str]] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        experiment_id: Optional[uuid.UUID] = None,
        source_run_id: Optional[uuid.UUID] = None,
        metric_name: Optional[str] = None,
        min_metric_value: Optional[float] = None,
        max_metric_value: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[ExperienceMemory]:
        """Retrieve memories by metadata filters only (no vector similarity)."""
        conditions = [
            ExperienceMemory.workspace_id == workspace_id,
            ExperienceMemory.status == status.value,
        ]

        if memory_types:
            conditions.append(ExperienceMemory.memory_type.in_([mt.value for mt in memory_types]))

        if task_types:
            conditions.append(ExperienceMemory.task_type.in_(task_types))

        if experiment_id:
            conditions.append(ExperienceMemory.experiment_id == experiment_id)

        if source_run_id:
            conditions.append(ExperienceMemory.source_run_id == source_run_id)

        if metric_name:
            conditions.append(ExperienceMemory.metric_name == metric_name)

        if min_metric_value is not None:
            conditions.append(ExperienceMemory.achieved_metric_value >= min_metric_value)

        if max_metric_value is not None:
            conditions.append(ExperienceMemory.achieved_metric_value <= max_metric_value)

        order_column = getattr(ExperienceMemory, order_by, ExperienceMemory.created_at)
        if order_desc:
            order_column = order_column.desc()

        query = (
            select(ExperienceMemory)
            .where(and_(*conditions))
            .order_by(order_column)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_memory_by_id(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Get a memory entry by ID."""
        query = select(ExperienceMemory).where(
            ExperienceMemory.id == memory_id,
            ExperienceMemory.workspace_id == workspace_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_memory(
        self,
        memory_id: uuid.UUID,
        workspace_id: uuid.UUID,
        updates: Dict[str, Any],
    ) -> Optional[ExperienceMemory]:
        """Update a memory entry."""
        memory = await self.get_memory_by_id(memory_id, workspace_id)
        if not memory:
            return None

        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)

        memory.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def update_access_stats(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Update access count and last accessed timestamp."""
        memory = await self.get_memory_by_id(memory_id, workspace_id)
        if not memory:
            return None

        memory.access_count += 1
        memory.last_accessed_at = datetime.utcnow()
        await self.session.flush()
        return memory

    async def archive_memory(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Archive a memory entry."""
        return await self.update_memory(
            memory_id,
            workspace_id,
            {"status": MemoryStatus.ARCHIVED.value, "archived_at": datetime.utcnow()},
        )

    async def deprecate_memory(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Deprecate a memory entry."""
        return await self.update_memory(
            memory_id,
            workspace_id,
            {"status": MemoryStatus.DEPRECATED.value},
        )

    async def reactivate_memory(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExperienceMemory]:
        """Reactivate an archived/deprecated memory."""
        return await self.update_memory(
            memory_id,
            workspace_id,
            {"status": MemoryStatus.ACTIVE.value, "archived_at": None},
        )

    async def delete_memory(
        self, memory_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> bool:
        """Delete a memory entry."""
        memory = await self.get_memory_by_id(memory_id, workspace_id)
        if not memory:
            return False
        await self.session.delete(memory)
        await self.session.flush()
        return True

    async def count_memories(
        self,
        workspace_id: uuid.UUID,
        memory_types: Optional[List[MemoryType]] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
    ) -> int:
        """Count memories matching criteria."""
        conditions = [
            ExperienceMemory.workspace_id == workspace_id,
            ExperienceMemory.status == status.value,
        ]

        if memory_types:
            conditions.append(ExperienceMemory.memory_type.in_([mt.value for mt in memory_types]))

        query = select(func.count(ExperienceMemory.id)).where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_memory_stats(self, workspace_id: uuid.UUID) -> Dict[str, Any]:
        """Get memory statistics for a workspace."""
        total = await self.count_memories(workspace_id)
        active = await self.count_memories(workspace_id, status=MemoryStatus.ACTIVE)
        archived = await self.count_memories(workspace_id, status=MemoryStatus.ARCHIVED)
        deprecated = await self.count_memories(workspace_id, status=MemoryStatus.DEPRECATED)

        type_counts = {}
        for mem_type in MemoryType:
            count = await self.count_memories(
                workspace_id, memory_types=[mem_type], status=MemoryStatus.ACTIVE
            )
            type_counts[mem_type.value] = count

        return {
            "total": total,
            "active": active,
            "archived": archived,
            "deprecated": deprecated,
            "by_type": type_counts,
        }