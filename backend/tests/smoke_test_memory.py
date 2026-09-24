#!/usr/bin/env python
"""Smoke test for Phase 13 Experience Memory System.

Tests the complete flow:
1. Store memory entries with embeddings
2. Generate embeddings via embedding service
3. Retrieve similar memories via semantic similarity
4. Test metadata filtering
5. Test memory ranking
6. Test memory lifecycle (archive, deprecate, reactivate)
"""

import asyncio
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import init_engine, get_db
from app.engine.memory.embeddings import embedding_service
from app.engine.memory.ranking import CompositeRanking, get_ranking_strategy
from app.engine.memory.retrieval import MemoryContext, MemoryRetrievalService
from app.engine.memory.storage import MemoryStorageService
from app.models.memory import ExperienceMemory, MemoryStatus, MemoryType


async def test_embedding_generation():
    """Test embedding generation."""
    print("\n=== Testing Embedding Generation ===")
    texts = [
        "Classification task with tabular dataset using gradient boosting",
        "Regression task with time series data using LSTM",
        "Image classification using CNN with data augmentation",
    ]
    embeddings = await embedding_service.embed(texts)
    print(f"Generated {len(embeddings)} embeddings")
    print(f"Embedding dimension: {len(embeddings[0])}")
    print(f"Model: {embedding_service.model_name}")
    assert len(embeddings) == 3
    assert len(embeddings[0]) == embedding_service.dimension
    print("[OK] Embedding generation works")
    return embeddings


async def _get_or_create_workspace(session: AsyncSession) -> uuid.UUID:
    """Get or create a test workspace."""
    from app.models.workspace import Workspace
    from app.models.user import User
    from sqlalchemy import text
    
    # Use raw SQL to avoid relationship loading issues
    result = await session.execute(text("SELECT id FROM workspaces LIMIT 1"))
    row = result.first()
    if row:
        return row[0]
    
    # Create a test user with unique email
    user_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO users (id, email, name, email_verified, is_active, created_at, updated_at) "
             "VALUES (:id, :email, :name, :email_verified, :is_active, :created_at, :updated_at)"),
        {
            "id": user_id,
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "name": "Test User",
            "email_verified": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    
    # Create workspace
    workspace_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO workspaces (id, owner_id, name, description, meta, created_at, updated_at) "
             "VALUES (:id, :owner_id, :name, :description, :meta, :created_at, :updated_at)"),
        {
            "id": workspace_id,
            "owner_id": user_id,
            "name": "Test Workspace",
            "description": "Smoke test workspace",
            "meta": "{}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    await session.commit()
    return workspace_id


async def test_store_and_retrieve():
    """Test storing and retrieving memories."""
    print("\n=== Testing Store and Retrieve ===")
    async for session in get_db():
        workspace_id = await _get_or_create_workspace(session)
        storage = MemoryStorageService(session)

        # Create test dataset fingerprint
        fingerprint = {
            "name": "test_dataset",
            "n_features": 20,
            "n_rows": 1000,
            "target_type": "binary",
        }

        # Store a successful experiment memory
        memory1 = await storage.store_experiment_outcome(
            workspace_id=workspace_id,
            experiment_id=None,
            source_run_id=None,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            solution_strategy="XGBoost with early stopping, max_depth=6, learning_rate=0.1",
            metric_name="accuracy",
            metric_value=0.92,
            success=True,
            memory_metadata={"hyperparameters": {"max_depth": 6, "learning_rate": 0.1}},
        )
        print(f"Stored memory 1: {memory1.id} (type: {memory1.memory_type})")

        # Store a failed experiment memory
        memory2 = await storage.store_experiment_outcome(
            workspace_id=workspace_id,
            experiment_id=None,
            source_run_id=None,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            solution_strategy="Random Forest with default params",
            metric_name="accuracy",
            metric_value=0.78,
            success=False,
            memory_metadata={"hyperparameters": {}},
        )
        print(f"Stored memory 2: {memory2.id} (type: {memory2.memory_type})")

        # Store a dataset insight
        memory3 = await storage.store_dataset_insight(
            workspace_id=workspace_id,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            insight="High class imbalance (90/10), consider SMOTE or class weights",
            memory_metadata={"imbalance_ratio": 9.0},
        )
        print(f"Stored memory 3: {memory3.id} (type: {memory3.memory_type})")

        # Store a model selection experience
        memory4 = await storage.store_model_selection_experience(
            workspace_id=workspace_id,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            model_family="lightgbm",
            hyperparameters={"num_leaves": 31, "learning_rate": 0.05},
            metric_name="accuracy",
            metric_value=0.94,
            success=True,
            memory_metadata={"n_estimators": 100},
        )
        print(f"Stored memory 4: {memory4.id} (type: {memory4.memory_type})")

        # Store a preprocessing experience
        memory5 = await storage.store_preprocessing_experience(
            workspace_id=workspace_id,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            preprocessing_steps=["impute_median", "encode_categorical", "scale_standard"],
            metric_name="accuracy",
            metric_value=0.91,
            success=True,
            memory_metadata={"imputation_strategy": "median"},
        )
        print(f"Stored memory 5: {memory5.id} (type: {memory5.memory_type})")

        # Store a verified claim
        memory6 = await storage.store_verified_claim(
            workspace_id=workspace_id,
            claim="XGBoost outperforms Random Forest on tabular classification tasks with >1000 rows",
            evidence={"source": "benchmark_study_2024", "datasets_tested": 50},
            task_type="classification",
            dataset_fingerprint=fingerprint,
            experiment_id=None,
        )
        print(f"Stored memory 6: {memory6.id} (type: {memory6.memory_type})")

        # Store an agent decision
        memory7 = await storage.store_agent_decision(
            workspace_id=workspace_id,
            task_type="classification",
            dataset_fingerprint=fingerprint,
            agent_name="model_selector",
            decision_type="model_selection",
            rationale="Selected LightGBM for faster training with comparable accuracy",
            confidence=0.85,
            memory_metadata={"candidates": ["xgboost", "lightgbm", "catboost"]},
            experiment_id=None,
        )
        print(f"Stored memory 7: {memory7.id} (type: {memory7.memory_type})")

        await session.commit()

        # Test retrieval by similarity
        print("\n--- Testing Semantic Similarity Retrieval ---")
        query_embedding = await embedding_service.embed_single(
            "Classification task with tabular data using gradient boosting model"
        )
        similar = await storage.retrieve_similar(
            query_embedding=query_embedding,
            workspace_id=workspace_id,
            limit=5,
            status=MemoryStatus.ACTIVE,
        )
        print(f"Found {len(similar)} similar memories:")
        for mem, score in similar:
            print(f"  - {mem.id}: {mem.memory_type} (similarity: {score:.4f}) - {mem.solution_strategy[:60]}...")

        assert len(similar) > 0
        print("[OK] Semantic similarity retrieval works")

        # Test metadata filtering
        print("\n--- Testing Metadata Filtering ---")
        filtered = await storage.retrieve_by_metadata(
            workspace_id=workspace_id,
            memory_types=[MemoryType.SUCCESSFUL_EXPERIMENT, MemoryType.MODEL_SELECTION_EXPERIENCE],
            task_types=["classification"],
            status=MemoryStatus.ACTIVE,
            min_metric_value=0.9,
            limit=10,
        )
        print(f"Found {len(filtered)} filtered memories (successful + model selection, metric >= 0.9):")
        for mem in filtered:
            print(f"  - {mem.id}: {mem.memory_type}, metric={mem.achieved_metric_value}")

        assert len(filtered) >= 2
        print("[OK] Metadata filtering works")

        # Test memory lifecycle
        print("\n--- Testing Memory Lifecycle ---")
        # Archive a memory
        archived = await storage.archive_memory(memory2.id, workspace_id)
        assert archived is not None
        assert archived.status == MemoryStatus.ARCHIVED.value
        print(f"Archived memory {memory2.id}")

        # Verify archived memory not in active results
        active_memories = await storage.retrieve_by_metadata(
            workspace_id=workspace_id,
            status=MemoryStatus.ACTIVE,
        )
        archived_ids = [m.id for m in active_memories]
        assert memory2.id not in archived_ids
        print("[OK] Archived memory excluded from active results")

        # Reactivate
        reactivated = await storage.reactivate_memory(memory2.id, workspace_id)
        assert reactivated is not None
        assert reactivated.status == MemoryStatus.ACTIVE.value
        print(f"Reactivated memory {memory2.id}")

        # Test stats
        stats = await storage.get_memory_stats(workspace_id)
        print(f"Workspace stats: {stats}")
        # Just verify the structure is correct (counts may vary due to previous test runs)
        assert "total" in stats
        assert "active" in stats
        assert "archived" in stats
        assert "deprecated" in stats
        assert "by_type" in stats
        assert all(t in stats["by_type"] for t in [
            "verified_claim", "successful_experiment", "failed_experiment",
            "dataset_insight", "model_selection_experience", "preprocessing_experience", "agent_decision"
        ])
        print("[OK] Memory stats work")

        return workspace_id


async def test_retrieval_service():
    """Test high-level retrieval service."""
    print("\n=== Testing Retrieval Service ===")
    async for session in get_db():
        workspace_id = await _get_or_create_workspace(session)
        service = MemoryRetrievalService(session)

        fingerprint = {
            "name": "iris_dataset",
            "n_features": 4,
            "n_rows": 150,
            "target_type": "multiclass",
        }

        # Store some memories
        await service.store_experience(
            context=MemoryContext(
                task_type="classification",
                dataset_fingerprint=fingerprint,
                workspace_id=workspace_id,
                experiment_id=None,
            ),
            memory_type=MemoryType.SUCCESSFUL_EXPERIMENT,
            solution_strategy="SVM with RBF kernel, C=1.0, gamma=scale",
            achieved_metric_value=0.96,
            metric_name="accuracy",
            success=True,
        )

        await service.store_experience(
            context=MemoryContext(
                task_type="classification",
                dataset_fingerprint=fingerprint,
                workspace_id=workspace_id,
                experiment_id=None,
            ),
            memory_type=MemoryType.MODEL_SELECTION_EXPERIENCE,
            solution_strategy="Logistic Regression with L2 regularization",
            achieved_metric_value=0.94,
            metric_name="accuracy",
            memory_metadata={"model_family": "logistic_regression", "C": 1.0},
            success=True,
        )

        await session.commit()

        # Test retrieval with context
        context = MemoryContext(
            task_type="classification",
            dataset_fingerprint=fingerprint,
            workspace_id=workspace_id,
            context_type="experiment_planning",
            target_metric="accuracy",
            current_strategy="trying gradient boosting",
            max_results=5,
        )

        result = await service.retrieve_relevant_experiences(context)
        print(f"Retrieved {len(result.memories)} relevant memories in {result.retrieval_time_ms:.2f}ms")
        for rm in result.memories:
            print(f"  - {rm.memory.memory_type}: {rm.memory.solution_strategy[:50]}...")
            print(f"    similarity={rm.similarity_score:.4f}, ranking={rm.ranking_score:.4f}")
            print(f"    factors: {rm.rank_factors}")

        assert len(result.memories) > 0
        print("[OK] Retrieval service works")


async def test_ranking_strategies():
    """Test different ranking strategies."""
    print("\n=== Testing Ranking Strategies ===")
    async for session in get_db():
        workspace_id = await _get_or_create_workspace(session)
        storage = MemoryStorageService(session)

        fingerprint = {
            "name": "ranking_test",
            "n_features": 10,
            "n_rows": 500,
            "target_type": "binary",
        }

        # Store memories with different characteristics
        memories = []
        for i, (metric_val, strategy) in enumerate([
            (0.95, "Recent high-performing model"),
            (0.70, "Older low-performing model"),
            (0.85, "Medium performance"),
        ]):
            mem = await storage.store_experiment_outcome(
                workspace_id=workspace_id,
                experiment_id=None,
                source_run_id=None,
                task_type="classification",
                dataset_fingerprint=fingerprint,
                solution_strategy=strategy,
                metric_name="accuracy",
                metric_value=metric_val,
                success=metric_val > 0.8,
            )
            memories.append(mem)

        await session.commit()

        query_embedding = await embedding_service.embed_single(
            "Classification task looking for best model"
        )

        candidates = await storage.retrieve_similar(
            query_embedding=query_embedding,
            workspace_id=workspace_id,
            limit=10,
            status=MemoryStatus.ACTIVE,
        )

        print(f"Found {len(candidates)} candidates")

        # Test different ranking strategies
        query_context = {"context_type": "experiment_planning", "task_type": "classification"}

        strategies = [
            ("similarity", {}),
            ("recency_weighted", {"recency_weight": 0.5}),
            ("performance_weighted", {"performance_weight": 0.5}),
            ("access_frequency", {"popularity_weight": 0.5}),
            ("composite", {}),
        ]

        for strategy_name, kwargs in strategies:
            strategy = get_ranking_strategy(strategy_name, **kwargs)
            ranked = strategy.rank(candidates, query_context)
            print(f"\n{strategy_name}:")
            for i, rm in enumerate(ranked):
                print(f"  {i+1}. {rm.memory.solution_strategy[:40]} - "
                      f"sim={rm.similarity_score:.3f}, rank={rm.ranking_score:.3f}")

        print("[OK] Ranking strategies work")


async def test_retrieval_tool():
    """Test the agent-facing retrieval tool."""
    print("\n=== Testing Agent Retrieval Tool ===")
    from app.engine.tools.memory import RetrieveMemoryTool, StoreMemoryTool
    from app.db.session import get_db as get_db_session

    async for session in get_db_session():
        workspace_id = await _get_or_create_workspace(session)
        break

    # Store a memory using the tool
    store_tool = StoreMemoryTool()
    store_result = store_tool.run(
        type('Params', (), {
            'workspace_id': str(workspace_id),
            'experiment_id': None,
            'memory_type': 'successful_experiment',
            'task_type': 'classification',
            'dataset_fingerprint': {
                'name': 'tool_test',
                'n_features': 10,
                'n_rows': 100,
                'target_type': 'binary',
            },
            'solution_strategy': 'Tool-stored XGBoost model with tuned hyperparameters',
            'achieved_metric_value': 0.93,
            'metric_name': 'f1',
            'memory_metadata': {'stored_via': 'tool'},
            'success': True,
        })()
    )
    print(f"Store result: {store_result}")
    assert "memory_id" in store_result

    # Retrieve using the tool
    retrieve_tool = RetrieveMemoryTool()
    retrieve_result = retrieve_tool.run(
        type('Params', (), {
            'query': 'classification with gradient boosting',
            'limit': 5,
            'workspace_id': str(workspace_id),
            'task_type': 'classification',
            'context_type': 'experiment_planning',
            'min_similarity': 0.1,
            'ranking_strategy': 'composite',
        })()
    )
    print(f"Retrieve result: {retrieve_result}")
    assert "entries" in retrieve_result
    assert len(retrieve_result["entries"]) > 0
    print("[OK] Agent retrieval tool works")


async def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("PHASE 13 EXPERIENCE MEMORY SYSTEM - SMOKE TEST")
    print("=" * 60)

    # Initialize database
    init_engine()

    # Initialize embedding service
    embedding_service.initialize()

    try:
        await test_embedding_generation()
        await test_store_and_retrieve()
        await test_retrieval_service()
        await test_ranking_strategies()
        await test_retrieval_tool()

        print("\n" + "=" * 60)
        print("ALL SMOKE TESTS PASSED [OK]")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FAIL] SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await embedding_service.close()


if __name__ == "__main__":
    asyncio.run(main())