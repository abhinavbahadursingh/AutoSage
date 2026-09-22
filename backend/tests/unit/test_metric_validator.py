"""Unit tests for Metric Validator."""
from app.engine.verification.metric_validator import MetricValidator

def test_metric_validator_flags_suspicious_perfect_score():
    metrics = {"accuracy": 1.0, "val_loss": 0.05}
    passed, errors = MetricValidator.validate_metrics(metrics, "classification")
    assert passed is False
    assert any("Suspicious perfect score" in err for err in errors)

def test_metric_validator_accepts_valid_metrics():
    metrics = {"accuracy": 0.884, "val_loss": 0.32}
    passed, errors = MetricValidator.validate_metrics(metrics, "classification")
    assert passed is True
    assert len(errors) == 0
