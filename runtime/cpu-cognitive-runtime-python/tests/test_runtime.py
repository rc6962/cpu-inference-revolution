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
