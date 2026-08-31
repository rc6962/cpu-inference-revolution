#!/usr/bin/env python3
"""Quality scoring for benchmark results.

Category-specific scoring rules with explicit limitation labels.

Scoring strengths:
- calculation: STRONG (exact numeric, ±0.01 tolerance)
- extraction: STRONG (schema + numeric, ±0.01 tolerance)
- retrieval: MODERATE (source + key_fact substring gate)
- generation: WEAK (non-empty + min_length gate)

Limitations reported per category — substring matching is a regression gate,
not a quality measure.

Usage:
    python scripts/score_quality.py results_mode_a.json results_mode_b.json results_mode_c.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ── Scoring rules by category ──

def score_calculation(expected_fields: dict, output: str) -> dict:
    """STRONG: exact numeric match with ±0.01 tolerance.

    Limitation: only tests 2-number margin calculations.
    Does not test complex multi-step arithmetic.
    """
    expected = expected_fields.get("margin_pct")
    if expected is None:
        return {"pass": False, "reason": "no expected margin_pct", "strength": "STRONG"}

    # Extract number from output
    match = re.search(r"(\d+\.?\d*)\s*%", output)
    if not match:
        match = re.search(r"(\d+\.?\d*)", output)
    if not match:
        return {"pass": False, "reason": "no numeric value found in output", "strength": "STRONG"}

    actual = float(match.group(1))
    within_tolerance = abs(actual - expected) <= 0.01
    return {
        "pass": within_tolerance,
        "reason": f"expected {expected:.2f}%, got {actual:.2f}%",
        "strength": "STRONG",
        "limitation": "only tests 2-number margin calculations; does not test complex arithmetic",
    }


def score_extraction(expected_fields: dict, output: str) -> dict:
    """STRONG: JSON parse + required fields + numeric tolerance ±0.01.

    Limitation: only tests 3-field invoices.
    Does not test additional fields or tax calculation correctness.
    """
    # Try JSON parse
    try:
        parsed = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        # Fallback: extract JSON-like pattern
        json_match = re.search(r"\{[^}]+\}", output)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except (json.JSONDecodeError, TypeError):
                return {"pass": False, "reason": "output is not valid JSON", "strength": "STRONG"}
        else:
            return {"pass": False, "reason": "no JSON found in output", "strength": "STRONG"}

    # Check required fields
    required = ["vendor", "tax", "total"]
    missing = [f for f in required if f not in parsed]
    if missing:
        return {"pass": False, "reason": f"missing fields: {missing}", "strength": "STRONG"}

    # Numeric tolerance on tax and total
    issues = []
    for field in ["tax", "total"]:
        expected_val = expected_fields.get(field)
        actual_val = parsed.get(field)
        if expected_val is not None and actual_val is not None:
            if abs(float(actual_val) - float(expected_val)) > 0.01:
                issues.append(f"{field}: expected {expected_val}, got {actual_val}")

    # Vendor string match (normalized)
    expected_vendor = expected_fields.get("vendor", "")
    actual_vendor = parsed.get("vendor", "")
    if expected_vendor.lower() not in actual_vendor.lower() and actual_vendor.lower() not in expected_vendor.lower():
        issues.append(f"vendor: expected '{expected_vendor}', got '{actual_vendor}'")

    return {
        "pass": len(issues) == 0,
        "reason": "; ".join(issues) if issues else "all fields match",
        "strength": "STRONG",
        "limitation": "only tests 3-field invoices; does not test additional fields",
    }


def score_retrieval(expected_fields: dict, output: str) -> dict:
    """MODERATE: source_id substring + key_fact substring gate.

    Limitation: substring matching is a regression gate, not semantic correctness.
    Source name in output ≠ correct citation.
    """
    source_id = expected_fields.get("source_id", "")
    key_fact = expected_fields.get("key_fact", "")

    issues = []
    if source_id and source_id not in output:
        issues.append(f"source_id '{source_id}' not in output")
    if key_fact and key_fact.lower() not in output.lower():
        issues.append(f"key_fact '{key_fact}' not in output")

    return {
        "pass": len(issues) == 0,
        "reason": "; ".join(issues) if issues else "source and key fact present",
        "strength": "MODERATE",
        "limitation": "substring matching only; does not test semantic correctness or completeness",
    }


def score_generation(expected_fields: dict, output: str, input_text: str = "") -> dict:
    """WEAK: non-empty + min_length gate.

    Limitation: detects regressions only.
    Cannot claim equivalence or quality.
    """
    min_length = expected_fields.get("min_length", 20)
    non_empty = expected_fields.get("non_empty", True)

    issues = []
    if non_empty and not output.strip():
        issues.append("output is empty")
    if len(output.strip()) < min_length:
        issues.append(f"output length {len(output.strip())} < min_length {min_length}")
    if input_text and output.strip() == input_text.strip():
        issues.append("output is identical to input (no rewrite)")

    return {
        "pass": len(issues) == 0,
        "reason": "; ".join(issues) if issues else f"non-empty, length={len(output.strip())}",
        "strength": "WEAK",
        "limitation": "detects regressions only; cannot claim equivalence or quality",
    }


SCORERS = {
    "calculation": score_calculation,
    "extraction": score_extraction,
    "retrieval": score_retrieval,
    "generation": score_generation,
}


def score_case(case: dict, output: str) -> dict:
    """Score a single case against its expected output."""
    category = case["category"]
    scorer = SCORERS.get(category)
    if not scorer:
        return {"pass": False, "reason": f"unknown category: {category}", "strength": "NONE"}

    if category == "generation":
        return scorer(case.get("expected_fields", {}), output, case.get("input", ""))
    return scorer(case.get("expected_fields", {}), output)


def score_results(results_file: str) -> dict:
    """Score all results from a JSON results file."""
    with open(results_file) as f:
        data = json.load(f)
    results = data.get("results", data) if isinstance(data, dict) else data

    scored = []
    by_category = {}

    for r in results:
        case = r["case"]
        output = r.get("output", "")
        category = case["category"]

        score = score_case(case, output)
        scored.append({
            "id": case["id"],
            "category": category,
            "pass": score["pass"],
            "reason": score["reason"],
            "strength": score["strength"],
            "limitation": score.get("limitation", ""),
        })

        if category not in by_category:
            by_category[category] = {"total": 0, "pass": 0, "scores": []}
        by_category[category]["total"] += 1
        if score["pass"]:
            by_category[category]["pass"] += 1
        by_category[category]["scores"].append(score)

    summary = {}
    for cat, data in by_category.items():
        summary[cat] = {
            "total": data["total"],
            "pass": data["pass"],
            "pass_rate": f"{data['pass']/data['total']*100:.0f}%",
            "strength": data["scores"][0]["strength"] if data["scores"] else "NONE",
            "limitation": data["scores"][0].get("limitation", "") if data["scores"] else "",
        }

    return {"summary": summary, "details": scored}


def main():
    if len(sys.argv) < 2:
        print("Usage: python score_quality.py results_a.json [results_b.json] [results_c.json]")
        sys.exit(1)

    for path in sys.argv[1:]:
        print(f"\n{'='*60}")
        print(f"Scoring: {path}")
        print(f"{'='*60}")

        result = score_results(path)

        print(f"\n{'Category':<15} {'Pass':>5} {'Total':>5} {'Rate':>8} {'Strength':<10}")
        print("-" * 50)
        for cat, data in result["summary"].items():
            print(f"{cat:<15} {data['pass']:>5} {data['total']:>5} {data['pass_rate']:>8} {data['strength']:<10}")

        total_pass = sum(d["pass"] for d in result["summary"].values())
        total_all = sum(d["total"] for d in result["summary"].values())
        print("-" * 50)
        print(f"{'TOTAL':<15} {total_pass:>5} {total_all:>5} {total_pass/total_all*100:>7.0f}%")

        # Print limitations
        print(f"\nScoring limitations:")
        seen = set()
        for cat, data in result["summary"].items():
            lim = data.get("limitation", "")
            if lim and lim not in seen:
                print(f"  {cat}: {lim}")
                seen.add(lim)


if __name__ == "__main__":
    main()
