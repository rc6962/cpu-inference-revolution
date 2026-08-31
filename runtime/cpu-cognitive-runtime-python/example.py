#!/usr/bin/env python3
"""Run the CPU-native cognitive runtime demo.

This example uses the dependency-light demo modules in ``cognitive_runtime``.
It demonstrates:

* rule-based request analysis,
* deterministic calculation routing,
* retrieval plus answer generation,
* structured invoice extraction and verification, and
* verified exact-response caching.

Run from the project directory:

    cd /home/ubuntu/cpu-cognitive-runtime-python
    python3 example.py

You can also run it by absolute path because the project directory is added to
``sys.path`` below.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Iterable


# Make ``python3 /absolute/path/to/example.py`` work too.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_runtime.runtime import Request, Runtime, trace_to_dict  # noqa: E402


def build_demo_requests() -> list[Request]:
    """Return representative requests for each initial route family."""
    return [
        Request(
            request_id="req-calculation",
            session_id="session-1",
            text=(
                "What is the operating margin if revenue is 850000 "
                "and expenses are 612000?"
            ),
        ),
        Request(
            request_id="req-retrieval",
            session_id="session-2",
            text=(
                "According to the policy document, how many days of notice "
                "are required?"
            ),
        ),
        Request(
            request_id="req-invoice",
            session_id="session-3",
            text=(
                "Extract the invoice fields. Vendor: Example Co, "
                "Tax: 19.80, Total: 119.80"
            ),
            attachments=("invoice-001.txt",),
        ),
        Request(
            request_id="req-direct",
            session_id="session-4",
            text="Rewrite this sentence to sound more professional.",
        ),
    ]


def print_result(request: Request, runtime: Runtime) -> None:
    """Execute one request and print its analysis and execution trace."""
    analysis = runtime.analyze(request)
    result = runtime.execute(request)

    print(f"\n{'=' * 72}")
    print(f"Request: {request.request_id}")
    print(f"Input:   {request.text}")
    print("Analysis:")
    print(
        json.dumps(
            {
                "task_type": analysis.task_type,
                "risk_level": analysis.risk_level,
                "difficulty_band": analysis.difficulty_band,
                "requires_retrieval": analysis.requires_retrieval,
                "requires_tools": analysis.requires_tools,
                "recommended_route": analysis.recommended_route,
                "confidence": analysis.confidence,
                "reason_codes": analysis.reason_codes,
            },
            indent=2,
        )
    )
    print("Execution trace:")
    print(json.dumps(trace_to_dict(result), indent=2))


def main(requests: Iterable[Request] | None = None) -> None:
    """Run the demo and show a cache hit for a repeated request."""
    runtime = Runtime()
    demo_requests = list(requests or build_demo_requests())

    print("CPU-Native Cognitive Runtime demo")
    print(f"Project root: {PROJECT_ROOT}")
    print("This run uses deterministic placeholder modules; no external API is called.")

    for request in demo_requests:
        print_result(request, runtime)

    repeated_request = demo_requests[0]
    cached = runtime.execute(
        Request(
            request_id="req-calculation-repeat",
            session_id=repeated_request.session_id,
            text=repeated_request.text,
        )
    )

    print(f"\n{'=' * 72}")
    print("Cache demonstration")
    print(json.dumps({
        "original_request_id": repeated_request.request_id,
        "repeat_request_id": "req-calculation-repeat",
        "selected_route": cached.route,
        "status": cached.status,
        "output": cached.output,
    }, indent=2))


if __name__ == "__main__":
    main()
