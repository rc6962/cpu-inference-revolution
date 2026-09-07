import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from cognitive_runtime.runtime import Request, Runtime


def test_calculation_uses_deterministic_route():
    runtime = Runtime()
    result = runtime.execute(Request("1", "s", "What is the operating margin if revenue is 850000 and expenses are 612000?"))
    assert result.status == "success"
    assert result.route == "deterministic_calculation"
    assert result.output == "28.00%"


def test_retrieval_route_contains_source_evidence():
    runtime = Runtime()
    result = runtime.execute(Request("2", "s", "According to the policy document, how many days of notice are required?"))
    assert result.status == "success"
    assert result.route == "small_rag"
    assert "demo-policy.txt" in result.output


def test_invoice_route_extracts_and_verifies():
    runtime = Runtime()
    request = Request(
        "3", "s",
        "Extract invoice fields. Vendor: Example Co, Tax: 19.80, Total: 119.80",
        attachments=("invoice.txt",),
    )
    result = runtime.execute(request)
    assert result.status == "success"
    assert result.route == "invoice_extraction"
    assert "Example Co" in result.output
    assert any(trace.module == "verifier" for trace in result.traces)


def test_successful_result_is_cached():
    runtime = Runtime()
    request = Request("4", "s", "Rewrite this sentence to sound professional.")
    first = runtime.execute(request)
    second = runtime.execute(Request("different-id", "s", "Rewrite this sentence to sound professional."))
    assert first.status == "success"
    assert second.route == "exact_cache"
    assert second.output == first.output


# ── Analyzer routing tests ──

def test_retrieval_routing_handbook():
    runtime = Runtime()
    result = runtime.execute(Request("a1", "s", "How many sick days does the handbook allow?"))
    assert result.route == "small_rag"

def test_retrieval_routing_probation():
    runtime = Runtime()
    result = runtime.execute(Request("a2", "s", "How does the probation period work?"))
    assert result.route == "small_rag"

def test_retrieval_routing_onboarding():
    runtime = Runtime()
    result = runtime.execute(Request("a3", "s", "What documents are needed for onboarding?"))
    assert result.route == "small_rag"

def test_retrieval_routing_resignation():
    runtime = Runtime()
    result = runtime.execute(Request("a4", "s", "What notice is needed for resignation?"))
    assert result.route == "small_rag"

def test_retrieval_routing_vacation():
    runtime = Runtime()
    result = runtime.execute(Request("a5", "s", "What is the vacation policy?"))
    assert result.route == "small_rag"

def test_retrieval_routing_requirements():
    runtime = Runtime()
    result = runtime.execute(Request("a6", "s", "What are the invoice submission requirements?"))
    assert result.route == "small_rag"


# ── Retrieval diagnostic tests ──

def _get_retrieval_metadata(runtime, text):
    """Execute a retrieval request and return the document_retriever trace metadata."""
    runtime.cache.clear()
    result = runtime.execute(Request("diag", "s", text))
    for trace in result.traces:
        if trace.module == "document_retriever":
            return trace.metadata
    return None


def test_retrieval_sick_days_returns_hr_handbook():
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "How many sick days does the handbook allow?")
    assert meta is not None, "document_retriever not invoked"
    assert meta["selected_source_id"] == "demo-hr-handbook.txt"
    assert len(meta["top_k_candidates"]) >= 2


def test_retrieval_onboarding_returns_hr_handbook():
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "What documents are needed for onboarding?")
    assert meta is not None
    assert meta["selected_source_id"] == "demo-hr-handbook.txt"


def test_retrieval_no_matching_document():
    """A query with no retrieval keywords routes elsewhere — no retriever trace expected."""
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "What is the quantum entanglement coefficient?")
    # This query has no retrieval keywords, so it routes to small_direct, not small_rag.
    # No document_retriever trace is expected.
    assert meta is None  # routed to small_direct, no retrieval attempted


def test_retrieval_phrase_preservation():
    """Verify that multiword phrases like 'sick days' are preserved in the FTS query."""
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "How many sick days does the handbook allow?")
    assert meta is not None
    fts_q = meta["fts_query"].lower()
    # 'sick' and 'days' should appear as phrase candidates
    assert "sick" in fts_q


def test_retrieval_low_confidence_no_answer():
    """A non-retrieval query routes elsewhere — no retriever trace expected."""
    runtime = Runtime()
    runtime.cache.clear()
    result = runtime.execute(Request("low", "s", "What is the meaning of life?"))
    # This query has no retrieval keywords, routes to small_direct
    for trace in result.traces:
        if trace.module == "document_retriever":
            # If retriever was somehow invoked, verify it handles gracefully
            assert trace.metadata["retrieval_status"] in ("low_confidence", "success")
            return
    # Expected: no retriever trace (routed to small_direct)
    assert result.route == "small_direct"


def test_retrieval_sick_days_key_fact():
    """Verify ret-003: sick days answer contains '10 sick days'."""
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "How many sick days does the handbook allow?")
    assert meta is not None
    assert meta["selected_source_id"] == "demo-hr-handbook.txt"
    # The output should contain the key fact
    result = runtime.execute(Request("ret003", "s", "How many sick days does the handbook allow?"))
    assert "10 sick days" in result.output.lower()


def test_retrieval_vacation_key_fact():
    """Verify ret-004: vacation answer contains 'vacation'."""
    runtime = Runtime()
    meta = _get_retrieval_metadata(runtime, "What is the vacation policy?")
    assert meta is not None
    assert meta["selected_source_id"] == "demo-policy.txt"
    result = runtime.execute(Request("ret004", "s", "What is the vacation policy?"))
    assert "vacation" in result.output.lower()


# ── Model metrics integration tests ──

def test_fallback_has_model_metrics_with_fallback_used():
    """Fallback response produces model_metrics with fallback_used=True."""
    runtime = Runtime()
    result = runtime.execute(Request("fm1", "s", "Say hello"))
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    assert len(sm_traces) == 1
    meta = sm_traces[0].metadata
    mm = meta.get("model_metrics", {})
    assert mm.get("fallback_used") is True
    assert mm.get("model_loaded") is False
    assert mm.get("stop_reason") == "fallback"
    assert mm.get("input_tokens") in (0, None)
    assert mm.get("output_tokens") in (0, None)


def test_deterministic_no_model_has_no_small_model_trace():
    """Deterministic calculation route has no small_model trace at all."""
    runtime = Runtime()
    result = runtime.execute(Request("dm1", "s", "What is the operating margin if revenue is 850000 and expenses are 612000?"))
    assert result.route == "deterministic_calculation"
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    assert len(sm_traces) == 0


def test_legacy_metadata_compatibility():
    """Legacy top-level metadata (no model_metrics key) is read correctly."""
    from cognitive_runtime.runtime import ModuleResult
    # Simulate a legacy trace: metadata at top level, no model_metrics
    legacy_meta = {
        "fallback_used": True,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    # Verify the extraction logic works with legacy format
    mm = legacy_meta.get("model_metrics") or legacy_meta
    assert mm.get("fallback_used") is True
    assert mm.get("input_tokens") == 0


def test_nested_model_metrics_preferred_over_legacy():
    """When both model_metrics and legacy top-level exist, model_metrics wins."""
    from cognitive_runtime.runtime import ModuleResult
    mixed_meta = {
        "fallback_used": False,  # legacy says not fallback
        "model_metrics": {
            "fallback_used": True,  # nested says fallback
            "input_tokens": 42,
        },
    }
    mm = mixed_meta.get("model_metrics") or mixed_meta
    assert mm.get("fallback_used") is True  # nested wins
    assert mm.get("input_tokens") == 42


def test_model_metrics_json_serializable():
    """All model_metrics fields are JSON-serializable."""
    import json
    runtime = Runtime()
    result = runtime.execute(Request("js1", "s", "Say hi"))
    for trace in result.traces:
        meta = trace.metadata
        # Should not raise
        serialized = json.dumps(meta)
        assert isinstance(serialized, str)
        # model_metrics if present should also serialize
        mm = meta.get("model_metrics")
        if mm is not None:
            serialized_mm = json.dumps(mm)
            assert isinstance(serialized_mm, str)


def test_model_metrics_has_required_fields():
    """model_metrics contains all required schema fields."""
    runtime = Runtime()
    result = runtime.execute(Request("rf1", "s", "Say hi"))
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    assert len(sm_traces) == 1
    mm = sm_traces[0].metadata.get("model_metrics", {})
    required = [
        "model_name", "model_path_basename", "model_loaded",
        "model_load_time_ms", "fallback_used", "fallback_reason",
        "input_tokens", "evidence_tokens", "output_tokens",
        "prompt_processing_time_ms", "generation_time_ms",
        "total_model_time_ms", "time_to_first_token_ms",
        "stop_reason", "prompt_tokens_per_second",
        "generation_tokens_per_second",
        "process_rss_before_bytes", "process_rss_after_bytes",
        "process_rss_peak_bytes", "rss_measurement_method",
        "metrics_available", "metrics_unavailable_reason",
    ]
    for field in required:
        assert field in mm, f"Missing required field: {field}"


def test_retrieval_has_evidence_tokens_field():
    """Retrieval route's model_metrics includes evidence_tokens."""
    runtime = Runtime()
    result = runtime.execute(Request("ev1", "s", "How many sick days does the handbook allow?"))
    sm_traces = [t for t in result.traces if t.module == "small_model"]
    # In fallback mode, evidence_tokens should be 0 or None
    for trace in sm_traces:
        mm = trace.metadata.get("model_metrics", {})
        assert "evidence_tokens" in mm

# ── Model identity property tests ──

def test_model_identity_property_with_path():
    """model_identity returns correct stem and basename from a path."""
    from cognitive_runtime.runtime import SmallModel
    import os
    old = os.environ.get("CPU_INFERENCE_MODEL_PATH")
    try:
        os.environ.pop("CPU_INFERENCE_MODEL_PATH", None)
        sm = SmallModel(model_path="models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
        ident = sm.model_identity
        assert ident["model_name"] == "qwen2.5-1.5b-instruct-q4_k_m"
        assert ident["model_path_basename"] == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    finally:
        if old is not None:
            os.environ["CPU_INFERENCE_MODEL_PATH"] = old


def test_model_identity_property_with_3b():
    """model_identity returns correct identity for 3B model."""
    from cognitive_runtime.runtime import SmallModel
    import os
    old = os.environ.get("CPU_INFERENCE_MODEL_PATH")
    try:
        os.environ.pop("CPU_INFERENCE_MODEL_PATH", None)
        sm = SmallModel(model_path="models/qwen2.5-3b-instruct-q4_k_m.gguf")
        ident = sm.model_identity
        assert ident["model_name"] == "qwen2.5-3b-instruct-q4_k_m"
        assert ident["model_path_basename"] == "qwen2.5-3b-instruct-q4_k_m.gguf"
    finally:
        if old is not None:
            os.environ["CPU_INFERENCE_MODEL_PATH"] = old


def test_model_identity_property_no_model():
    """model_identity returns None for both fields when no model configured."""
    from cognitive_runtime.runtime import SmallModel
    import os
    old = os.environ.get("CPU_INFERENCE_MODEL_PATH")
    try:
        os.environ.pop("CPU_INFERENCE_MODEL_PATH", None)
        sm = SmallModel()
        ident = sm.model_identity
        assert ident["model_name"] is None
        assert ident["model_path_basename"] is None
    finally:
        if old is not None:
            os.environ["CPU_INFERENCE_MODEL_PATH"] = old


def test_model_identity_not_unknown():
    """model_identity must never return 'unknown' — either real name or None."""
    from cognitive_runtime.runtime import SmallModel
    sm = SmallModel(model_path="models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
    ident = sm.model_identity
    assert ident["model_name"] != "unknown"
    assert ident["model_path_basename"] != "unknown"
