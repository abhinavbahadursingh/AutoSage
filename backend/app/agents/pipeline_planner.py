"""Pipeline Planner Agent — generates a well-defined pipeline from a natural language description.

This agent is separate from the experiment workflow agents. It takes a user's
experiment description and produces a structured pipeline plan (stages + edges)
that can be visualized interactively and optionally executed.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.llm.client import get_llm_client, run_coro_sync
from app.engine.llm.types import LLMError

logger = logging.getLogger("autosage.pipeline_planner")

STAGE = "pipeline_planner"


class PipelineStageOutput(BaseModel):
    """One stage in the generated pipeline."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique stage identifier (kebab-case)")
    name: str = Field(description="Human-readable stage name")
    agent: str = Field(description="Agent responsible for this stage")
    role: str = Field(description="Brief role description")
    description: str = Field(description="What this stage does")
    inputs: List[str] = Field(default_factory=list, description="Input names")
    outputs: List[str] = Field(default_factory=list, description="Output names")
    estimated_duration: str = Field(default="~1min", description="Rough time estimate")
    optional: bool = Field(default=False, description="Whether this stage can be skipped")


class PipelineEdgeOutput(BaseModel):
    """A directed edge between two stages."""

    model_config = ConfigDict(extra="forbid")

    from_stage: str = Field(description="Source stage id")
    to_stage: str = Field(description="Target stage id")
    label: str = Field(default="", description="Optional edge label")


class PipelinePlanOutput(AgentOutput):
    """Structured output: a complete pipeline plan."""

    task_type: str = Field(default="classification", description="Detected task type")
    target_metric: str = Field(default="accuracy", description="Suggested primary metric")
    complexity: str = Field(default="medium", description="low | medium | high")
    stages: List[PipelineStageOutput] = Field(default_factory=list)
    edges: List[PipelineEdgeOutput] = Field(default_factory=list)
    summary: str = Field(default="", description="Human-readable pipeline summary")
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


_SYSTEM = (
    "You are the AutoSage Pipeline Planner. "
    "Given a natural language description of an ML experiment, design a well-defined "
    "pipeline with clear stages, data flow, and agent assignments. "
    "Return JSON matching the provided schema exactly."
)


def _detect_task_type(description: str) -> str:
    """Heuristic task type detection from description."""
    d = description.lower()
    if any(w in d for w in ["regress", "forecast", "predict price", "estimate", "eta", "minutes", "amount", "revenue", "sales"]):
        return "regression"
    if any(w in d for w in ["classify", "classification", "churn", "fraud", "default", "readmit", "click", "convert", "binary"]):
        return "binary_classification"
    if any(w in d for w in ["multi-label", "multi class", "route", "ticket", "tag", "label", "category", "topic"]):
        return "multi_class_classification"
    if any(w in d for w in ["cluster", "segment", "group", "anomaly", "outlier"]):
        return "unsupervised"
    return "classification"


def _detect_metric(description: str, task_type: str) -> str:
    """Heuristic metric detection."""
    d = description.lower()
    if "recall" in d:
        return "recall"
    if "precision" in d:
        return "precision"
    if "calibrat" in d or "probab" in d or "auc" in d:
        return "roc_auc"
    if "f1" in d:
        return "f1"
    if "mae" in d or "mean absolute" in d:
        return "mae"
    if "rmse" in d or "root mean" in d:
        return "rmse"
    if "r2" in d or "r-squared" in d:
        return "r2"
    if task_type == "regression":
        return "mae"
    return "accuracy"


def _detect_complexity(description: str) -> str:
    """Estimate pipeline complexity."""
    d = description.lower()
    score = 0
    if any(w in d for w in ["compare", "several", "multiple", "search", "tune", "optimize"]):
        score += 1
    if any(w in d for w in ["calibrat", "drift", "leakage", "fairness", "explain"]):
        score += 1
    if any(w in d for w in ["deploy", "monitor", "serve", "api", "endpoint"]):
        score += 1
    if any(w in d for w in ["deep learning", "neural", "transformer", "llm", "embedding"]):
        score += 1
    if len(d) > 200:
        score += 1
    if score >= 3:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def _build_heuristic_stages(task_type: str, description: str) -> List[PipelineStageOutput]:
    """Build a sensible default pipeline when no LLM is available."""
    d = description.lower()
    wants_compare = any(w in d for w in ["compare", "several", "multiple", "search", "tune"])
    wants_calibration = any(w in d for w in ["calibrat", "probab", "auc"])
    wants_drift = any(w in d for w in ["drift", "monitor", "psi"])
    wants_explain = any(w in d for w in ["explain", "shap", "feature importance", "interpret"])

    stages: List[PipelineStageOutput] = [
        PipelineStageOutput(
            id="data_ingestion",
            name="Data Ingestion",
            agent="Data Scout",
            role="retrieval · validation",
            description="Locate, load, and validate the dataset from the registry or upload.",
            inputs=["dataset_name"],
            outputs=["raw_dataset", "schema"],
            estimated_duration="~30s",
        ),
        PipelineStageOutput(
            id="profiling",
            name="Profiling",
            agent="Profiler",
            role="statistics · schema",
            description="Compute column statistics, missing rates, class balance, and drift signals.",
            inputs=["raw_dataset"],
            outputs=["profile_report", "target_column"],
            estimated_duration="~1min",
        ),
        PipelineStageOutput(
            id="preprocessing",
            name="Preprocessing",
            agent="Preprocessor",
            role="cleaning · encoding",
            description="Impute missing values, encode categoricals, scale features, and split train/test.",
            inputs=["raw_dataset", "profile_report"],
            outputs=["train_dataset", "test_dataset", "preprocessor"],
            estimated_duration="~1min",
        ),
        PipelineStageOutput(
            id="model_selection",
            name="Model Selection",
            agent="Model Selector",
            role="search · ranking",
            description="Shortlist and rank candidate model families for the task and budget.",
            inputs=["train_dataset", "target_column"],
            outputs=["model_shortlist", "model_spec"],
            estimated_duration="~30s",
        ),
    ]

    if wants_compare:
        stages.append(
            PipelineStageOutput(
                id="hyperparameter_search",
                name="Hyperparameter Search",
                agent="Experimenter",
                role="optimization · cv",
                description="Run cross-validated hyperparameter search across the shortlist.",
                inputs=["train_dataset", "model_shortlist"],
                outputs=["best_params", "cv_results"],
                estimated_duration="~5min",
            )
        )

    stages.append(
        PipelineStageOutput(
            id="training",
            name="Training",
            agent="Trainer",
            role="fit · checkpoint",
            description="Fit the selected model(s) on the full training set with the best parameters.",
            inputs=["train_dataset", "model_spec"],
            outputs=["trained_model", "training_metrics"],
            estimated_duration="~2min",
        )
    )

    stages.append(
        PipelineStageOutput(
            id="evaluation",
            name="Evaluation",
            agent="Evaluator",
            role="metrics · slices",
            description="Score the model on the holdout set and compute slice-level metrics.",
            inputs=["trained_model", "test_dataset"],
            outputs=["metrics", "evaluation_report"],
            estimated_duration="~1min",
        )
    )

    if wants_calibration:
        stages.append(
            PipelineStageOutput(
                id="calibration",
                name="Calibration",
                agent="Calibrator",
                role="probability · calibration",
                description="Calibrate predicted probabilities using isotonic or Platt scaling.",
                inputs=["trained_model", "test_dataset"],
                outputs=["calibrated_model"],
                estimated_duration="~1min",
                optional=True,
            )
        )

    if wants_explain:
        stages.append(
            PipelineStageOutput(
                id="explainability",
                name="Explainability",
                agent="Explainer",
                role="shap · interpretation",
                description="Compute SHAP values and feature importance for model interpretation.",
                inputs=["trained_model", "test_dataset"],
                outputs=["shap_values", "feature_importance"],
                estimated_duration="~2min",
                optional=True,
            )
        )

    if wants_drift:
        stages.append(
            PipelineStageOutput(
                id="drift_detection",
                name="Drift Detection",
                agent="Monitor",
                role="drift · psi",
                description="Compute PSI and other drift metrics between training and serving distributions.",
                inputs=["train_dataset", "test_dataset"],
                outputs=["drift_report", "psi_scores"],
                estimated_duration="~1min",
                optional=True,
            )
        )

    stages.append(
        PipelineStageOutput(
            id="verification",
            name="Verification",
            agent="Verifier",
            role="claims · evidence",
            description="Recompute metrics, check for data leakage, and verify pipeline claims.",
            inputs=["metrics", "evaluation_report", "trained_model"],
            outputs=["verification_report", "passed"],
            estimated_duration="~1min",
        )
    )

    stages.append(
        PipelineStageOutput(
            id="pipeline_freeze",
            name="Pipeline Freeze",
            agent="Orchestrator",
            role="freeze · export",
            description="Package the verified pipeline for deployment and export artifacts.",
            outputs=["frozen_pipeline", "deployment_bundle"],
            estimated_duration="~30s",
        )
    )

    return stages


def _build_heuristic_edges(stages: List[PipelineStageOutput]) -> List[PipelineEdgeOutput]:
    """Build linear edges between consecutive stages."""
    edges: List[PipelineEdgeOutput] = []
    for i in range(len(stages) - 1):
        edges.append(
            PipelineEdgeOutput(
                from_stage=stages[i].id,
                to_stage=stages[i + 1].id,
            )
        )
    return edges


class PipelinePlannerAgent(BaseAgent):
    """Generates a structured pipeline plan from a natural language description."""

    stage = STAGE
    output_model = PipelinePlanOutput

    def __init__(
        self,
        llm: Optional[Any] = None,
        tools: Optional[Any] = None,
    ) -> None:
        super().__init__(llm=llm, tools=tools)

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        config = state.get("config") or {}
        description = config.get("prompt", "") or state.get("description", "")
        dataset = config.get("dataset_name", "") or config.get("dataset", "")
        target = config.get("target_column", "")

        user = (
            f"Design a pipeline for this experiment:\n\n"
            f"Description: {description}\n"
        )
        if dataset:
            user += f"Dataset: {dataset}\n"
        if target:
            user += f"Target column: {target}\n"
        user += (
            "\nReturn a JSON object with stages, edges, and metadata. "
            "Each stage must have a unique id, name, agent, role, description, "
            "inputs, outputs, and estimated_duration. "
            "Edges connect stages by their ids."
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Deterministic fallback when no LLM is available."""
        config = state.get("config") or {}
        description = config.get("prompt", "") or state.get("description", "")
        task_type = _detect_task_type(description)
        metric = _detect_metric(description, task_type)
        complexity = _detect_complexity(description)

        stages = _build_heuristic_stages(task_type, description)
        edges = _build_heuristic_edges(stages)

        return PipelinePlanOutput(
            source="heuristic",
            task_type=task_type,
            target_metric=metric,
            complexity=complexity,
            stages=stages,
            edges=edges,
            summary=f"Auto-generated {task_type} pipeline with {len(stages)} stages.",
            assumptions=[
                "Dataset is tabular (CSV/Parquet)",
                "Sufficient compute budget for training",
                "Target column exists in the dataset",
            ],
            risks=[
                "Data quality issues may require additional cleaning",
                "Class imbalance may need resampling",
                "Model performance may not meet thresholds",
            ],
        )

    def run(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Execute the agent: LLM first, heuristic fallback when allowed."""
        from app.core.config import settings

        client = self._client()
        if not client.has_providers():
            if not settings.LLM_ALLOW_HEURISTIC_FALLBACK:
                from app.engine.llm.types import LLMUnavailableError
                raise LLMUnavailableError(
                    f"{self.stage}: no LLM providers configured and heuristic fallback disabled"
                )
            logger.warning("pipeline_planner: no LLM providers, using heuristic fallback")
            return self.heuristic(state)

        try:
            system, user = self.build_prompts(state)
            output = client.complete_structured_sync(
                system=system,
                user=user,
                response_model=self.output_model,
                model_tier="fast",
            )
            if not output.source or output.source == "llm":
                output.source = "llm"
            return output
        except LLMError as exc:
            if not settings.LLM_ALLOW_HEURISTIC_FALLBACK:
                raise
            logger.warning("pipeline_planner: LLM failed (%s), using heuristic fallback", exc)
            return self.heuristic(state)

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, PipelinePlanOutput)
        return {
            "pipeline_plan": {
                "task_type": output.task_type,
                "target_metric": output.target_metric,
                "complexity": output.complexity,
                "stages": [s.model_dump() for s in output.stages],
                "edges": [e.model_dump() for e in output.edges],
                "summary": output.summary,
                "assumptions": output.assumptions,
                "risks": output.risks,
                "source": output.source,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, PipelinePlanOutput)
        return f"pipeline plan generated: {len(output.stages)} stages, {len(output.edges)} edges"


def pipeline_planner_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`PipelinePlannerAgent`."""
    return PipelinePlannerAgent().node_update(state)


__all__ = [
    "PipelinePlannerAgent",
    "PipelinePlanOutput",
    "PipelineStageOutput",
    "PipelineEdgeOutput",
    "pipeline_planner_node",
]
