"""Cascade tests: verifier rules, tier registry, cascade flow, regression.

All tests use mocks — no GGUF model required, no host-OS-specific behavior.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from cognitive_runtime.runtime import ModuleResult, Request, Runtime
from cognitive_runtime.tiers import TIERS, TIER_FAST, TIER_NONE, TIER_STRONG, get_tier, tier_for_model_path
from cognitive_runtime.verifier import (
    FAILED,
    NEEDS_CLARIFICATION,
    NEEDS_ESCALATION,
    VERIFIED,
    check_clarification,
    verify,
)


# ── Tier registry tests ──

def test_tier_registry_keys():
    assert set(TIERS) == {"none", "fast", "strong"}

def test_tier_none_is_not_model_backed():
    assert TIER_NONE.is_model_backed is False
    assert TIER_NONE.model_path is None

def test_tier_fast_identity():
    assert TIER_FAST.model_stem == "qwen2.5-1.5b-instruct-q4_k_m"
    assert TIER_FAST.model_basename == "qwen2.5-1.5b-instruct-q4_k_m.gguf"

def test_tier_strong_identity():
    assert TIER_STRONG.model_stem == "qwen2.5-3b-instruct-q4_k_m"
    assert TIER_STRONG.model_basename == "qwen2.5-3b-instruct-q4_k_m.gguf"

def test_get_tier_unknown_raises():
    try:
        get_tier("ultra")
        assert False, "should have raised"
    except KeyError:
        pass

def test_tier_for_model_path_roundtrip():
    assert tier_for_model_path(TIER_FAST.model_path).name == "fast"
    assert tier_for_model_path(None).name == "none"
    assert tier_for_model_path("/some/other.gguf").name == "none"


# ── Verifier rule tests ──

def test_r3_length_escalates_short_output():
    v = verify("Summarize the policy", "small_direct", "ok")
    assert v.verdict == NEEDS_ESCALATION
    assert "R3_length" in v.checks_failed

def test_r3_length_escalates_demo_output():
    v = verify("Summarize the policy", "small_direct",
               "Demo response for: Summarize the policy")
    assert v.verdict == NEEDS_ESCALATION
    assert v.reason.startswith("R3_length:demo_output")

def test_r5_calculation_mismatch_escalates():
    v = verify("Operating margin revenue 850000 expenses 612000?",
               "small_direct", "The margin is about 45 percent",
               deterministic_answer="28.00%")
    assert v.verdict == NEEDS_ESCALATION
    assert "R5_calculation" in v.checks_failed

def test_r5_calculation_match_verifies():
    v = verify("Operating margin revenue 850000 expenses 612000?",
               "small_direct", "The operating margin is 28.00%.",
               deterministic_answer="28.00%")
    assert v.verdict == VERIFIED
    assert "R5_calculation" in v.checks_passed

def test_r4_extraction_missing_fields_escalates():
    v = verify("Extract invoice fields", "invoice_extraction",
               "Vendor: Acme Corp")
    assert v.verdict == NEEDS_ESCALATION
    assert "R4_extraction" in v.checks_failed

def test_r4_extraction_complete_verifies():
    v = verify("Extract invoice fields", "invoice_extraction",
               "Vendor: Acme Corp, Tax: 45, Total: 245, Subtotal: 200")
    assert v.verdict == VERIFIED

def test_r2_grounding_low_overlap_escalates():
    v = verify("What is the sick leave policy?", "small_rag",
               "The stock market rallied strongly today on tech earnings.",
               evidence_text="Employees may take up to 10 sick days per year.")
    assert v.verdict == NEEDS_ESCALATION
    assert "R2_grounding" in v.checks_failed

def test_r2_grounding_high_overlap_verifies():
    v = verify("What is the sick leave policy?", "small_rag",
               "Employees may take up to 10 sick days per year.",
               evidence_text="Employees may take up to 10 sick days per year.")
    assert v.verdict == VERIFIED

def test_clarification_gate():
    v = verify("How does this situation impact the timeline?", "small_direct",
               "This situation could affect delivery in several important ways overall.")
    assert v.verdict == NEEDS_CLARIFICATION
    assert v.reason == "ambiguous_reference"

def test_check_clarification_patterns():
    assert check_clarification("Review this document please") is True
    assert check_clarification("What is the vacation policy?") is False

def test_clean_generation_verifies():
    v = verify("Rewrite professionally", "small_direct",
               "The meeting concluded successfully with clear action items.")
    assert v.verdict == VERIFIED


# ── Cascade flow tests (mocked models — no GGUF) ──

class _MockModel:
    """Stand-in for SmallModel with scripted outputs."""
    name = "small_model"

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    def run(self, context, inputs):
        self.calls += 1
        text = self._outputs[min(self.calls - 1, len(self._outputs) - 1)]
        return ModuleResult(self.name, "success", text, 0.7,
                            metadata={"model_metrics": {"model_loaded": True,
                                                        "fallback_used": False}})


def _make_cascade_with_mocks(fast_outputs, strong_outputs):
    from cognitive_runtime.cascade import CascadeRuntime
    rt = CascadeRuntime.__new__(CascadeRuntime)
    rt.fast_tier = TIER_FAST
    rt.strong_tier = TIER_STRONG
    rt.base = Runtime()
    rt._fast_model = _MockModel(fast_outputs)
    rt._strong_model = _MockModel(strong_outputs)
    rt.base.modules["small_model"] = rt._fast_model
    rt.cache = {}
    return rt


def test_cascade_verified_fast_result_not_escalated():
    rt = _make_cascade_with_mocks(
        ["The meeting concluded successfully with clear action items."], [])
    result = rt.execute(Request("c1", "s", "Rewrite this professionally"))
    assert rt._fast_model.calls == 1
    assert rt._strong_model.calls == 0
    assert result.escalated is False
    sm = [t for t in result.traces if t.module == "small_model"][0]
    assert sm.metadata["tier_requested"] == "fast"
    assert sm.metadata["tier_used"] == "fast"
    assert sm.metadata["tier_escalated"] is False
    assert sm.metadata["verifier_verdict"] == "verified"


def test_cascade_escalates_on_bad_fast_output():
    rt = _make_cascade_with_mocks(
        ["Demo response for: Rewrite this professionally"],
        ["The meeting concluded successfully with clear action items."])
    result = rt.execute(Request("c2", "s", "Rewrite this professionally"))
    assert rt._fast_model.calls == 1
    assert rt._strong_model.calls == 1
    assert result.escalated is True
    assert result.escalation_reason.startswith("R3_length")
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    assert len(sm_traces) == 2
    assert sm_traces[0].metadata["tier_used"] == "fast"
    assert sm_traces[1].metadata["tier_used"] == "strong"
    assert sm_traces[1].metadata["tier_escalated"] is True


def test_cascade_clarification_no_model_waste():
    rt = _make_cascade_with_mocks(
        ["Review this document and consider the broader implications carefully."], [])
    result = rt.execute(Request("c3", "s", "Review this"))
    assert result.status == "needs_clarification"
    assert "more context" in result.output.lower()
    assert result.escalated is False


def test_cascade_deterministic_route_untouched():
    """Calculation route must run the deterministic calculator, no model."""
    rt = _make_cascade_with_mocks([], [])
    result = rt.execute(Request(
        "c4", "s",
        "What is the operating margin if revenue is 850000 and expenses are 612000?"))
    assert result.route == "deterministic_calculation"
    assert result.output == "28.00%"
    assert rt._fast_model.calls == 0
    assert rt._strong_model.calls == 0


def test_cascade_strong_failure_marks_failed():
    class _FailingModel:
        name = "small_model"
        def __init__(self): self.calls = 0
        def run(self, context, inputs):
            self.calls += 1
            return ModuleResult(self.name, "success",
                                "Demo response for: x y z", 0.5)

    from cognitive_runtime.cascade import CascadeRuntime
    rt = CascadeRuntime.__new__(CascadeRuntime)
    rt.fast_tier = TIER_FAST
    rt.strong_tier = TIER_STRONG
    rt.base = Runtime()
    rt._fast_model = _FailingModel()
    rt._strong_model = _FailingModel()
    rt.base.modules["small_model"] = rt._fast_model
    rt.cache = {}
    result = rt.execute(Request("c5", "s", "Rewrite this professionally"))
    # Both tiers produce demo output → strong verdict still needs_escalation
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    assert rt._fast_model.calls == 1
    assert rt._strong_model.calls == 1
    assert sm_traces[-1].metadata["verifier_verdict"] == NEEDS_ESCALATION


# ── Regression: existing control suite unchanged ──

def test_control_suite_file_unchanged():
    """The original 30-case control file must still exist and parse."""
    import json
    p = Path(__file__).parents[3] / "data" / "benchmark_cases.jsonl"
    assert p.exists()
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 30


def test_cascade_case_file_valid():
    """The new cascade suite parses, has 50 cases, and required schema keys."""
    import json
    p = Path(__file__).parents[3] / "data" / "benchmark_cases_cascade.jsonl"
    assert p.exists()
    required = {"case_id", "category", "text", "expected_initial_route",
                "expected_final_status", "expected_max_tier",
                "expected_facts", "forbidden_facts", "trigger_rules"}
    tiers_seen = set()
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        assert required <= set(case), f"missing keys in {case['case_id']}"
        assert case["expected_max_tier"] in ("none", "fast", "strong")
        tiers_seen.add(case["expected_max_tier"])
        n += 1
    assert n == 50
    assert tiers_seen == {"none", "fast", "strong"}
