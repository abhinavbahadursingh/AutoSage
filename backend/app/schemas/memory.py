from pydantic import BaseModel
from typing import List, Dict, Any

class MemorySearchResult(BaseModel):
    task_type: str
    solution_strategy: str
    achieved_metric_value: float
    similarity_score: float
