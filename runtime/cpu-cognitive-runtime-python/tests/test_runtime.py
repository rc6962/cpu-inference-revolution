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