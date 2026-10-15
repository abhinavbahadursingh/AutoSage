"""Evidence category + verification level on every check.

The page distinguishes four kinds of evidence (repository source, synthetic
probe, this session's records, generated code) plus empirical runs, and it
must be able to do so for *all* 19 checks on *every* branch — PASS, FAIL,
NOT_VERIFIED and BLOCKED. A check that silently defaults to "source" would
let a fresh session's missing evidence read like repository proof, which is
exactly the lie the vocabulary section of the schema exists to prevent.
"""
from app.engine.objective_verification import checks as C
from app.engine.objective_verification.definitions import OBJECTIVES_BY_ID
from app.schemas.objective_verification import CheckStatus

CATEGORIES = {"source", "probe", "session", "generated", "empirical"}
LEVELS = {"source", "config", "generated", "runtime"}


def _all_check_ids():
    return [c.id for obj in OBJECTIVES_BY_ID.values() for c in obj.checks]


def test_every_check_is_covered_by_the_category_and_level_maps():
    ids = _all_check_ids()
    assert len(ids) == 19
    assert set(ids) == set(C._CHECK_CATEGORY), "every check needs a category"
    assert set(ids) == set(C._CHECK_LEVEL), "every check needs a verification level"
    assert set(C._CHECK_CATEGORY.values()) <= CATEGORIES
    assert set(C._CHECK_LEVEL.values()) <= LEVELS


def test_blocked_checks_carry_their_category_too():
    """The blocked branch goes through the same helper — it must not default."""
    result = C.blocked(
        "o4_decision_rationale",
        "Every decision records why it was made",
        "all decisions carry a rationale",
        "session input was rejected: too short",
    )
    assert result.status is CheckStatus.BLOCKED
    assert result.category == "session"
    assert result.verification_level == "runtime"


def test_source_pass_is_labelled_as_source_evidence():
    """A repository PASS must be identifiable as such, never as runtime proof."""
    result = C._result(
        "o2_specialist_agents",
        "The pipeline separates specialist agents",
        CheckStatus.PASS,
        expected="agents are separate",
        actual="agents are separate",
        evidence=["app/agents/*.py"],
        confidence=1.0,
    )
    assert result.category == "source"
    assert result.verification_level == "source"


def test_probe_check_is_labelled_as_a_synthetic_probe():
    result = C._result(
        "o1_dataset_driven_target",
        "The dataset drives target resolution",
        CheckStatus.NOT_VERIFIED,
        expected="target inferred",
        actual="no dataset",
        evidence=["no dataset"],
    )
    assert result.category == "probe"
    assert result.verification_level == "runtime"
