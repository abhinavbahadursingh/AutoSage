"""Metric Plausibility and Sanity Checker."""
from typing import Dict, Any, List, Tuple

class MetricValidator:
    @staticmethod
    def validate_metrics(metrics: Dict[str, float], task_type: str) -> Tuple[bool, List[str]]:
        errors = []
        for name, value in metrics.items():
            if "accuracy" in name.lower() or "f1" in name.lower() or "roc_auc" in name.lower():
                if value < 0.0 or value > 1.0:
                    errors.append(f"Impossible metric range: {name} = {value}")
                elif value == 1.0:
                    errors.append(f"Suspicious perfect score: {name} = 1.0 (Potential target leakage)")
        return len(errors) == 0, errors
