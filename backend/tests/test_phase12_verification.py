"""Phase 12 Verification Smoke Test.

Basic test to verify the Evidence & Verification System works end-to-end.
Run with: python -m pytest tests/test_phase12_verification.py -v
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as session_module
from app.engine.evidence.source import (
    EvidencePiece,
    EvidenceSearchResult,
    register_evidence_source,
    list_evidence_sources,
    clear_evidence_sources,
)
from app.engine.evidence.sources import (
    InternalEvidenceSource,
    MockExternalEvidenceSource,
)
from app.engine.verification.claims import (
    ClaimStatus,
    ClaimType,
    ExtractedClaim,
)
from app.engine.verification.engine import VerificationEngine
from app.engine.verification.extractors import (
    DecisionRecord,
    extract_all_claims,
)
from app.models.agent_execution import AgentExecution
from app.models.decision import Decision
from app.models.evidence import EvidenceTrailNode
from app.models.experiment import Experiment
from app.models.workspace import Workspace
from app.models.user import User


def get_db_session() -> AsyncSession:
    """Create a database session for testing."""
    session_module.init_engine()
    return session_module.AsyncSessionLocal()


async def create_test_setup(session: AsyncSession, include_evidence: bool = False) -> dict:
    """Create test user, workspace, experiment, agent execution, decision, and optionally evidence."""
    # Create user with unique email
    unique_id = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        email=f"test_{unique_id}@autosage.local",
        name=f"Test User {unique_id}",
        is_active=True,
    )
    session.add(user)

    # Create workspace
    workspace = Workspace(
        id=uuid4(),
        owner_id=user.id,
        name=f"Test Workspace {unique_id}",
        meta={},
    )
    session.add(workspace)

    # Create project
    from app.models.project import Project
    project = Project(
        id=uuid4(),
        user_id=user.id,
        name=f"Test Project {unique_id}",
        description="Test project",
    )
    session.add(project)

    # Create experiment
    experiment = Experiment(
        id=uuid4(),
        workspace_id=workspace.id,
        name=f"Test Experiment {unique_id}",
        description="Test experiment for verification",
        status="RUNNING",
        config={},
        max_retries=3,
    )
    session.add(experiment)

    # Create pipeline run if evidence is needed
    pipeline_run = None
    if include_evidence:
        from app.models.run import PipelineRun
        pipeline_run = PipelineRun(
            id=uuid4(),
            project_id=project.id,
            experiment_id=experiment.id,
            status="RUNNING",
            user_prompt="Test prompt",
        )
        session.add(pipeline_run)
        await session.flush()

    # Create agent execution
    agent_exec = AgentExecution(
        id=uuid4(),
        experiment_id=experiment.id,
        agent_name="model_selector",
        status="COMPLETED",
        attempt=1,
        input_payload={},
        output_payload={"model_family": "lightgbm"},
    )
    session.add(agent_exec)

    # Create decision with verifiable claims
    decision = Decision(
        id=uuid4(),
        experiment_id=experiment.id,
        agent_execution_id=agent_exec.id,
        decision_type="model_selection",
        rationale="Selected LightGBM with accuracy 0.92. The model beats baseline by 0.15. Cross-validation used for robust estimation.",
        confidence=0.9,
        payload={
            "model_family": "lightgbm",
            "metrics": {"accuracy": 0.92, "f1": 0.89},
        },
    )
    session.add(decision)

    # Create evidence trail node if needed
    if include_evidence and pipeline_run:
        evidence_node = EvidenceTrailNode(
            id=uuid4(),
            run_id=pipeline_run.id,
            agent_name="model_selector",
            decision_type="model_selection",
            rationale="LightGBM achieves accuracy 0.92 with stratified cross-validation. Baseline random forest accuracy 0.77.",
            empirical_evidence={
                "model": "lightgbm",
                "accuracy": 0.92,
                "baseline_accuracy": 0.77,
                "cv_folds": 5,
            },
        )
        session.add(evidence_node)

    await session.commit()

    return {
        "user": user,
        "workspace": workspace,
        "project": project,
        "experiment": experiment,
        "agent_execution": agent_exec,
        "decision": decision,
        "pipeline_run": pipeline_run,
    }


class TestEvidenceSources:
    """Test evidence source implementations."""

    @pytest.mark.asyncio
    async def test_mock_external_evidence_source(self):
        """Test mock external evidence source."""
        source = MockExternalEvidenceSource()
        result = await source.search("accuracy", limit=5)

        assert isinstance(result, EvidenceSearchResult)
        assert result.query == "accuracy"
        assert len(result.pieces) >= 1
        piece = result.pieces[0]
        assert piece.source_id == "mock_external"
        assert piece.source_type == "external"
        assert piece.credibility_score > 0

    @pytest.mark.asyncio
    async def test_evidence_source_registry(self):
        """Test evidence source registration and listing."""
        clear_evidence_sources()

        session = get_db_session()
        # Create minimal setup for internal source
        setup = await create_test_setup(session, include_evidence=True)
        try:
            # Register test sources
            internal = InternalEvidenceSource(session)
            mock = MockExternalEvidenceSource()

            register_evidence_source(internal)
            register_evidence_source(mock)

            sources = list_evidence_sources()
            assert len(sources) == 2
            assert any(s.source_id == "internal_evidence_trail" for s in sources)
            assert any(s.source_id == "mock_external" for s in sources)
        finally:
            await session.close()


class TestClaimExtraction:
    """Test claim extraction from decisions."""

    @pytest.mark.asyncio
    async def test_extract_metric_claims(self):
        """Test extraction of metric performance claims."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            decision = setup["decision"]
            record = DecisionRecord(
                decision_id=decision.id,
                experiment_id=decision.experiment_id,
                agent_execution_id=decision.agent_execution_id,
                agent_name="model_selector",
                decision_type=decision.decision_type,
                rationale=decision.rationale,
                confidence=decision.confidence,
                payload=decision.payload,
                created_at=decision.created_at,
            )

            claims = extract_all_claims(record)

            # Should extract metric claims
            metric_claims = [c for c in claims if c.claim_type == ClaimType.METRIC_PERFORMANCE]
            assert len(metric_claims) >= 1
            assert any("accuracy" in c.text.lower() for c in metric_claims)
            assert any("f1" in c.text.lower() for c in metric_claims)
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_extract_baseline_comparison(self):
        """Test extraction of baseline comparison claims."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            decision = setup["decision"]
            record = DecisionRecord(
                decision_id=decision.id,
                experiment_id=decision.experiment_id,
                agent_execution_id=decision.agent_execution_id,
                agent_name="model_selector",
                decision_type=decision.decision_type,
                rationale=decision.rationale,
                confidence=decision.confidence,
                payload=decision.payload,
                created_at=decision.created_at,
            )

            claims = extract_all_claims(record)

            baseline_claims = [c for c in claims if c.claim_type == ClaimType.BASELINE_COMPARISON]
            assert len(baseline_claims) >= 1
            assert "baseline" in baseline_claims[0].text.lower()
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_extract_method_validity(self):
        """Test extraction of method validity claims."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            decision = setup["decision"]
            record = DecisionRecord(
                decision_id=decision.id,
                experiment_id=decision.experiment_id,
                agent_execution_id=decision.agent_execution_id,
                agent_name="model_selector",
                decision_type=decision.decision_type,
                rationale=decision.rationale,
                confidence=decision.confidence,
                payload=decision.payload,
                created_at=decision.created_at,
            )

            claims = extract_all_claims(record)

            method_claims = [c for c in claims if c.claim_type == ClaimType.METHOD_VALIDITY]
            assert len(method_claims) >= 1
            assert "cross-validation" in method_claims[0].text.lower()
        finally:
            await session.close()


class TestVerificationEngine:
    """Test the verification engine end-to-end."""

    @pytest.mark.asyncio
    async def test_verify_single_decision(self):
        """Test verifying a single decision."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            engine = VerificationEngine(session, min_evidence_credibility=0.5)

            decision = setup["decision"]
            record = DecisionRecord(
                decision_id=decision.id,
                experiment_id=decision.experiment_id,
                agent_execution_id=decision.agent_execution_id,
                agent_name="model_selector",
                decision_type=decision.decision_type,
                rationale=decision.rationale,
                confidence=decision.confidence,
                payload=decision.payload,
                created_at=decision.created_at,
            )

            response = await engine.verify_decision(record)

            assert response.total_claims > 0
            assert response.overall_status in (ClaimStatus.VERIFIED, ClaimStatus.UNVERIFIED, ClaimStatus.CONFLICT)
            assert 0.0 <= response.overall_confidence <= 1.0

            # Should have at least one verified or unverified claim
            assert response.verified_count + response.unverified_count + response.conflict_count == response.total_claims
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_verify_experiment(self):
        """Test verifying all decisions in an experiment."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            engine = VerificationEngine(session)

            exp_id = setup["experiment"].id
            response = await engine.verify_experiment_decisions(exp_id)

            assert response.total_claims > 0
            assert response.overall_status in (ClaimStatus.VERIFIED, ClaimStatus.UNVERIFIED, ClaimStatus.CONFLICT)
        finally:
            await session.close()


class TestEndToEndVerification:
    """End-to-end verification flow tests."""

    @pytest.mark.asyncio
    async def test_full_verification_flow(self):
        """Test the complete flow: Decision -> Claims -> Evidence -> Verification."""
        session = get_db_session()
        setup = await create_test_setup(session, include_evidence=True)
        try:
            # 1. Extract claims from decision
            decision = setup["decision"]
            record = DecisionRecord(
                decision_id=decision.id,
                experiment_id=decision.experiment_id,
                agent_execution_id=decision.agent_execution_id,
                agent_name="model_selector",
                decision_type=decision.decision_type,
                rationale=decision.rationale,
                confidence=decision.confidence,
                payload=decision.payload,
                created_at=decision.created_at,
            )

            claims = extract_all_claims(record)
            assert len(claims) > 0

            # 2. Verify claims using engine
            engine = VerificationEngine(session, min_evidence_credibility=0.5)
            from app.engine.verification.claims import ClaimVerificationRequest
            request = ClaimVerificationRequest(claims=claims, min_credibility=0.5)
            response = await engine.verify_claims(request)

            # 3. Verify response structure
            assert response.total_claims == len(claims)
            assert response.overall_status in (
                ClaimStatus.VERIFIED,
                ClaimStatus.UNVERIFIED,
                ClaimStatus.CONFLICT,
                ClaimStatus.REJECTED,
            )

            # 4. Each result should have proper structure
            for result in response.results:
                assert result.claim_id is not None
                assert result.claim_text
                assert result.claim_type in ClaimType
                assert result.status in ClaimStatus
                assert 0.0 <= result.confidence_score <= 1.0
                assert isinstance(result.supporting_evidence, list)
                assert isinstance(result.contradicting_evidence, list)
                assert isinstance(result.reasoning, str)
                assert result.verified_at is not None
        finally:
            await session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])