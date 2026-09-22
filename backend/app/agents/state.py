"""AutoSage Global State Schema for LangGraph."""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator

class EvidenceNode(TypedDict):
    node_id: str
    parent_id: Optional[str]
    agent_name: str
    decision_type: str
    rationale: str
    empirical_evidence: Dict[str, Any]
    timestamp: str

class AutoSageState(TypedDict):
    run_id: str
    project_id: str
    user_prompt: str
    
    raw_dataset_path: str
    dataset_metadata: Dict[str, Any]
    data_profile: Dict[str, Any]
    
    ml_task_type: str
    target_column: str
    evaluation_metric: str
    split_strategy: Dict[str, Any]
    
    preprocessing_code: str
    model_code: str
    execution_script: str
    
    container_exit_code: Optional[int]
    execution_logs: List[str]
    experiment_metrics: Dict[str, float]
    model_artifact_path: Optional[str]
    
    verification_passed: bool
    verification_errors: List[str]
    retry_count: int
    max_retries: int
    
    evidence_trail: Annotated[List[EvidenceNode], operator.add]
    relevant_past_experiences: List[Dict[str, Any]]
