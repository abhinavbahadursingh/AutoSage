"""Pipeline Planner endpoint.

POST /pipeline/plan  -> generate a pipeline plan from a description
GET  /pipeline/status -> check if the planner is available
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.agents.pipeline_planner import PipelinePlannerAgent, PipelinePlanOutput
from app.agents.state import ExperimentWorkflowState

router = APIRouter()


class PipelinePlanRequest(BaseModel):
    """Request body for pipeline plan generation."""

    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Natural language description of the experiment",
    )
    dataset_name: Optional[str] = Field(
        default=None,
        description="Optional dataset name to include in planning context",
    )
    target_column: Optional[str] = Field(
        default=None,
        description="Optional target column name",
    )
    task_type: Optional[str] = Field(
        default=None,
        description="Optional task type hint (classification, regression, etc.)",
    )


class PipelineStageResponse(BaseModel):
    """One stage in the pipeline plan."""

    id: str
    name: str
    agent: str
    role: str
    description: str
    inputs: list[str]
    outputs: list[str]
    estimated_duration: str
    optional: bool


class PipelineEdgeResponse(BaseModel):
    """A directed edge between stages."""

    from_stage: str
    to_stage: str
    label: str


class PipelinePlanResponse(BaseModel):
    """Complete pipeline plan response."""

    task_type: str
    target_metric: str
    complexity: str
    stages: list[PipelineStageResponse]
    edges: list[PipelineEdgeResponse]
    summary: str
    assumptions: list[str]
    risks: list[str]
    source: str


@router.post(
    "/plan",
    response_model=PipelinePlanResponse,
    summary="Generate a pipeline plan from a description",
)
async def generate_pipeline_plan(
    payload: PipelinePlanRequest,
    user: CurrentUser,
) -> PipelinePlanResponse:
    """Generate a structured pipeline plan from a natural language description.

    Uses the PipelinePlannerAgent to analyze the description and produce
    a well-defined pipeline with stages, edges, and metadata.
    """
    # Build a minimal workflow state for the agent
    state: ExperimentWorkflowState = {
        "experiment_id": "pipeline-planner",
        "workspace_id": "pipeline-planner",
        "config": {
            "prompt": payload.description,
            "dataset_name": payload.dataset_name or "",
            "target_column": payload.target_column or "",
            "task_type": payload.task_type or "",
        },
    }

    agent = PipelinePlannerAgent()
    output = agent.run(state)

    assert isinstance(output, PipelinePlanOutput)

    return PipelinePlanResponse(
        task_type=output.task_type,
        target_metric=output.target_metric,
        complexity=output.complexity,
        stages=[PipelineStageResponse(**s.model_dump()) for s in output.stages],
        edges=[PipelineEdgeResponse(**e.model_dump()) for e in output.edges],
        summary=output.summary,
        assumptions=output.assumptions,
        risks=output.risks,
        source=output.source,
    )


@router.get("/status", summary="Check pipeline planner availability")
async def pipeline_status(user: CurrentUser) -> dict:
    """Return whether the pipeline planner is available."""
    from app.engine.llm.client import get_llm_client

    client = get_llm_client()
    has_providers = client.has_providers()

    return {
        "available": True,
        "llm_available": has_providers,
        "fallback_enabled": True,
    }
