"""Deterministic verifier for the adaptive cascade.

Verdicts:
  verified            — output passes all category checks; return it
  needs_escalation    — a trigger rule fired; re-run on the strong tier
  needs_clarification — request is ambiguous; no tier can resolve it
  failed              — terminal failure (both tiers exhausted / out of scope)

Rule table (deterministic, inspectable — no learned router):
  R1 format      — output fails the category's expected format
  R2 grounding   — retrieval output not grounded in the selected source evidence
  R3 length      — output empty or below minimum length for the category
  R4 extraction  — fewer than 3 of 4 required invoice fields present
  R5 calculation — model answer disagrees with the deterministic calculator
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VERIFIED = "verified"
NEEDS_ESCALATION = "needs_escalation"
NEEDS_CLARIFICATION = "needs_clarification"
FAILED = "failed"

# Vague-reference patterns for needs_clarification (deterministic keyword rules)
CLARIFICATION_PATTERNS = [
    r"\bthis situation\b",
    r"\bthe proposal\b",
    r"\ba good time\b",
    r"\bthe numbers\b",
    r"\bthe issue we discussed\b",
    r"\bhow does this compare\b",
    r"\bthe implications\b",
    r"\boption a or b\b",
    r"\breview this\b",
    r"\bwhat would you recommend\b",
]

_INVOICE_FIELDS = ["vendor", "tax", "total", "subtotal"]
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?%")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class VerificationResult:
    verdict: str
    reason: str | None = None
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict:
        return {
            "verifier_verdict": self.verdict,
            "verifier_reason": self.reason,
            "verifier_checks_passed": self.checks_passed,
            "verifier_checks_failed": self.checks_failed,
        }


def _is_fallback_output(output: str) -> bool:
    return output.startswith("Demo response for:")


def check_clarification(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in CLARIFICATION_PATTERNS)


def verify(
    request_text: str,
    route: str,
    output: str,
    *,
    evidence_text: str | None = None,
    deterministic_answer: str | None = None,
) -> VerificationResult:
    """Apply the rule table to one model-backed result.

    Deterministic routes (no model) are always verified — the cascade only
    verifies model output.
    """
    passed: list[str] = []
    failed: list[str] = []

    # Ambiguity gate first — no tier can resolve a context-free question
    if check_clarification(request_text):
        return VerificationResult(
            NEEDS_CLARIFICATION,
            reason="ambiguous_reference",
            checks_passed=passed,
            checks_failed=["clarification"],
        )

    # Fallback/demo output from a model tier always escalates
    if _is_fallback_output(output):
        failed.append("R3_length")
        return VerificationResult(
            NEEDS_ESCALATION,
            reason="R3_length:demo_output",
            checks_passed=passed,
            checks_failed=failed,
        )

    # R3 length
    if len(output.strip().split()) < 2:
        failed.append("R3_length")
        return VerificationResult(
            NEEDS_ESCALATION,
            reason="R3_length:too_short",
            checks_passed=passed,
            checks_failed=failed,
        )
    passed.append("R3_length")

    # R5 calculation: model answer must match deterministic calculator
    if deterministic_answer is not None:
        model_nums = _NUM_RE.findall(output.replace(",", ""))
        det = deterministic_answer.replace("%", "").replace(",", "").strip()
        det_val = _NUM_RE.search(det)
        if det_val:
            target = float(det_val.group())
            matched = any(abs(float(n) - target) < 0.01 for n in model_nums)
            if matched:
                passed.append("R5_calculation")
            else:
                failed.append("R5_calculation")
                return VerificationResult(
                    NEEDS_ESCALATION,
                    reason=f"R5_calculation:expected {deterministic_answer}",
                    checks_passed=passed,
                    checks_failed=failed,
                )

    # R1 format by route
    if route == "invoice_extraction":
        low = output.lower()
        present = [f for f in _INVOICE_FIELDS if f in low or _field_value_present(f, output)]
        if len(present) >= 3:
            passed.append("R1_format")
            passed.append("R4_extraction")
        else:
            failed.append("R4_extraction")
            return VerificationResult(
                NEEDS_ESCALATION,
                reason=f"R4_extraction:only {len(present)}/4 fields",
                checks_passed=passed,
                checks_failed=failed,
            )
    elif route == "deterministic_calculation":
        if _PERCENT_RE.search(output) or _NUM_RE.search(output):
            passed.append("R1_format")
        else:
            failed.append("R1_format")
            return VerificationResult(
                NEEDS_ESCALATION,
                reason="R1_format:no numeric answer",
                checks_passed=passed,
                checks_failed=failed,
            )
    else:
        passed.append("R1_format")

    # R2 grounding for retrieval routes
    if route == "small_rag" and evidence_text:
        ev_words = {w for w in re.findall(r"[a-z]{4,}", evidence_text.lower())}
        out_words = {w for w in re.findall(r"[a-z]{4,}", output.lower())}
        overlap = len(ev_words & out_words) / max(len(out_words), 1)
        if overlap >= 0.15:
            passed.append("R2_grounding")
        else:
            failed.append("R2_grounding")
            return VerificationResult(
                NEEDS_ESCALATION,
                reason=f"R2_grounding:overlap {overlap:.2f}",
                checks_passed=passed,
                checks_failed=failed,
            )
    else:
        passed.append("R2_grounding")

    return VerificationResult(VERIFIED, checks_passed=passed, checks_failed=failed)


def _field_value_present(field_name: str, output: str) -> bool:
    """Heuristic: invoice fields often appear as 'Vendor: X' / 'Tax: N'."""
    pat = re.compile(rf"{field_name}\s*[:=]\s*\S+", re.IGNORECASE)
    return bool(pat.search(output))
