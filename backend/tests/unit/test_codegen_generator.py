"""LLM-backed code generation for the Objective Verification page.

Three things are asserted here, because they are the contract the page
depends on:

1. Generation really goes through the configured provider — the canned reply
   of a fake client is parsed, and nothing else can produce files.
2. When no provider is available the generator reports a **real** error. It
   never falls back to templates and never presents a template as model
   output.
3. The structured decision record is only accepted when the model actually
   produced one; a malformed reply yields no record rather than a plausible
   default.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app.engine.codegen.generator import (
    DesignRecord,
    generate_async,
    parse_design,
    parse_generated_files,
)


# ── parsing ───────────────────────────────────────────────────────────────


def test_parse_generated_files_reads_file_markers():
    text = (
        "--- FILE: pipeline.py ---\nprint('hi')\n"
        "--- FILE: config.yaml ---\ntest_size: 0.2\n"
    )
    files = parse_generated_files(text)
    assert [f.name for f in files] == ["pipeline.py", "config.yaml"]
    assert files[0].language == "python"
    assert files[1].language == "yaml"
    assert "test_size: 0.2" in files[1].content


def test_parse_generated_files_falls_back_to_fences():
    text = "```python\nimport sklearn\n```"
    files = parse_generated_files(text)
    assert len(files) == 1
    assert files[0].name == "pipeline.py"


def test_parse_generated_files_returns_empty_when_nothing_usable():
    assert parse_generated_files("I could not help with that.") == []


def test_parse_design_accepts_a_full_record():
    record = parse_design(
        json.dumps(
            {
                "algorithm": "xgboost",
                "hyperparameters": {"max_depth": 6},
                "metrics": {"primary": "roc_auc"},
                "validation_strategy": "5-fold",
                "assumptions": ["binary target"],
                "alternatives": ["logreg"],
                "decisions": [
                    {
                        "category": "ALGORITHM",
                        "decision": "xgboost",
                        "rationale": "handles imbalance",
                        "confidence": "0.7",
                        "source": "literature",
                    }
                ],
            }
        )
    )
    assert isinstance(record, DesignRecord)
    assert record.algorithm == "xgboost"
    decision = record.decisions[0]
    assert decision.category == "algorithm"  # normalised
    assert decision.confidence == 0.7  # numeric string coerced


def test_parse_design_rejects_prose_and_keeps_optional_fields_optional():
    assert parse_design("Sure! I'd start with gradient boosting.") is None

    record = parse_design(json.dumps({"algorithm": "rf", "decisions": []}))
    assert record is not None
    assert record.validation_strategy is None
    assert record.assumptions == []


def test_confidence_out_of_range_or_unusable_becomes_none():
    record = parse_design(
        json.dumps(
            {
                "decisions": [
                    {"decision": "a", "confidence": 7},
                    {"decision": "b", "confidence": "high"},
                    {"decision": "c"},
                ]
            }
        )
    )
    assert record is not None
    assert [d.confidence for d in record.decisions] == [None, None, None]


# ── generation through a provider ─────────────────────────────────────────


class _NoProvider:
    def has_providers(self) -> bool:
        return False


class _GoodProvider:
    provider = "groq"
    model = "groq/test-model"

    def has_providers(self) -> bool:
        return True

    async def complete(self, *, system, user, **kwargs):
        return SimpleNamespace(
            text=(
                "--- FILE: pipeline.py ---\n"
                '"""Generated, never executed."""\n'
                "MODEL = 1\n"
            ),
            model=self.model,
            provider=self.provider,
        )

    async def complete_structured(self, *, system, user, response_model, **kwargs):
        return response_model.model_validate(
            json.loads(
                '{"algorithm": "rf", "decisions": [{"category": "algorithm",'
                ' "decision": "rf", "rationale": "robust"}]}'
            )
        )


class _ProviderWithoutDesign(_GoodProvider):
    async def complete_structured(self, *, system, user, response_model, **kwargs):
        raise RuntimeError("model replied with prose, not JSON")


class _RateLimited(_GoodProvider):
    async def complete(self, *, system, user, **kwargs):
        from app.engine.llm.types import LLMUnavailableError

        raise LLMUnavailableError("all providers failed: 429 rate limited")


def _run(coro):
    return asyncio.run(coro)


def test_generate_without_provider_reports_a_real_error(monkeypatch):
    """No provider -> FAILED with a specific message, never a template."""
    monkeypatch.setattr("app.engine.codegen.generator.get_llm_client", lambda: _NoProvider())
    result = _run(generate_async("Predict customer churn", None))
    assert result.status == "FAILED"
    assert result.files == []
    assert result.design is None
    assert "GROQ_API_KEY" in result.message  # actionable, not "something went wrong"


def test_generate_parses_the_provider_reply(monkeypatch):
    monkeypatch.setattr("app.engine.codegen.generator.get_llm_client", lambda: _GoodProvider())
    result = _run(generate_async("Predict customer churn", "churn.csv"))
    assert result.status == "OK"
    assert [f.name for f in result.files] == ["pipeline.py"]
    assert result.provider == "groq"
    assert result.model == "groq/test-model"
    assert result.design is not None
    assert result.design.algorithm == "rf"
    assert result.decisions[0]["decision"] == "rf"
    # provenance is recorded, so the page can say where the record came from
    assert any("groq" in line for line in result.activity)


def test_generate_surfaces_provider_failure(monkeypatch):
    monkeypatch.setattr("app.engine.codegen.generator.get_llm_client", lambda: _RateLimited())
    result = _run(generate_async("Predict customer churn", None))
    assert result.status == "FAILED"
    assert result.files == []
    assert "429" in result.message or "LLM" in result.message


def test_design_failure_does_not_fabricate_a_record(monkeypatch):
    """Code stands on its own; a bad decision reply means *no* decision."""
    monkeypatch.setattr(
        "app.engine.codegen.generator.get_llm_client", lambda: _ProviderWithoutDesign()
    )
    result = _run(generate_async("Predict customer churn", None))
    assert result.status == "OK"
    assert [f.name for f in result.files] == ["pipeline.py"]
    assert result.design is None
    assert result.decisions == []
    assert any("Decision record unavailable" in a for a in result.activity)


def test_short_problem_statement_is_rejected_before_any_call(monkeypatch):
    class _Exploding(_GoodProvider):
        def has_providers(self) -> bool:  # pragma: no cover - must not run
            raise AssertionError("provider must not be consulted")

    monkeypatch.setattr("app.engine.codegen.generator.get_llm_client", lambda: _Exploding())
    result = _run(generate_async("hi", None))
    assert result.status == "FAILED"
    assert "too short" in result.message
