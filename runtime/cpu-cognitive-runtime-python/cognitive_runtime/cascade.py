"""Adaptive cascade runtime: fast tier first, verifier decides, strong tier on escalation.

Policy (deterministic):
  1. Deterministic/no-model routes (tier "none") run unchanged — no model call.
  2. Model-backed routes run on the FAST tier (1.5B) first.
  3. The verifier applies rules R1–R5 to the fast-tier output.
  4. Only on needs_escalation is the request re-run on the STRONG tier (3B).
  5. needs_clarification returns a clarification prompt (no escalation).

Trace fields added to every cascade result:
  tier_requested, tier_used, tier_escalated, escalation_reason
plus the verifier metadata (verifier_verdict, checks_passed/failed).
"""
from __future__ import annotations

import time
from typing import Any

from .runtime import (
    ExecutionResult,
    Request,
    Runtime,
    SmallModel,
)
from .tiers import TIER_FAST, TIER_STRONG, TIER_NONE, TierSpec
from .verifier import (
    NEEDS_CLARIFICATION,
    NEEDS_ESCALATION,
    VERIFIED,
    VerificationResult,
    verify,
)

MODEL_BACKED_ROUTES = {"small_rag", "small_direct"}

CLARIFICATION_PROMPT = (
    "I need more context to answer that. Could you specify the subject, "
    "document, or decision this refers to?"
)


class CascadeRuntime:
    """Two-tier adaptive runtime over the existing single-model Runtime."""

    def __init__(self, fast_tier: TierSpec = TIER_FAST, strong_tier: TierSpec = TIER_STRONG):
        self.fast_tier = fast_tier
        self.strong_tier = strong_tier
        self.base = Runtime()
        # Replace the default SmallModel with the fast tier by default
        self._fast_model = SmallModel(model_path=fast_tier.model_path)
        self._strong_model = SmallModel(model_path=strong_tier.model_path)
        self.base.modules["small_model"] = self._fast_model
        self.cache: dict[str, ExecutionResult] = {}

    # ── public API mirrors Runtime.execute ──

    def execute(self, request: Request, use_cache: bool = True) -> ExecutionResult:
        key = request.text.strip().lower()
        if use_cache and key in self.cache:
            cached = self.cache[key]
            return ExecutionResult(
                request.request_id, cached.status, cached.output,
                "exact_cache", cached.traces,
            )

        analysis = self.base.analyze(request)
        route = analysis.recommended_route

        # Tier "none": deterministic routes run unchanged
        if route not in MODEL_BACKED_ROUTES:
            result = self.base.execute(request, use_cache=False)
            self._annotate(result, tier_requested="none", tier_used="none",
                           escalated=False, reason=None, verdict=VERIFIED)
            if use_cache:
                self.cache[key] = result
            return result

        # Fast tier attempt
        self.base.modules["small_model"] = self._fast_model
        fast_result = self.base.execute(request, use_cache=False)
        evidence = self._get_evidence(request) if route == "small_rag" else None
        verdict = verify(
            request.text, route, fast_result.output, evidence_text=evidence,
        )

        if verdict.verdict == NEEDS_CLARIFICATION:
            result = ExecutionResult(
                request.request_id, "needs_clarification", CLARIFICATION_PROMPT,
                route, fast_result.traces,
            )
            self._annotate(result, "fast", "fast", False, verdict.reason, verdict)
            return result

        if verdict.verdict == VERIFIED:
            self._annotate(fast_result, "fast", "fast", False, None, verdict)
            self.cache[key] = fast_result
            return fast_result

        # Escalate to strong tier
        self.base.modules["small_model"] = self._strong_model
        try:
            strong_result = self.base.execute(request, use_cache=False)
        finally:
            self.base.modules["small_model"] = self._fast_model
        strong_evidence = self._get_evidence(request) if route == "small_rag" else None
        strong_verdict = verify(
            request.text, route, strong_result.output, evidence_text=strong_evidence,
        )
        # Annotate each attempt with its own tier, then merge traces
        self._annotate(fast_result, "fast", "fast", False, verdict.reason, verdict)
        self._annotate(strong_result, "fast", "strong", True, verdict.reason, strong_verdict)
        merged = ExecutionResult(
            request.request_id,
            strong_result.status,
            strong_result.output,
            strong_result.route,
            fast_result.traces + strong_result.traces,
            escalated=True,
            escalation_reason=verdict.reason,
        )
        if strong_verdict.verdict == VERIFIED:
            self.cache[key] = merged
        return merged

    # ── helpers ──

    def _get_evidence(self, request: Request) -> str | None:
        """Run the deterministic retriever to obtain full evidence text."""
        try:
            from .runtime import ExecutionContext
            ctx = ExecutionContext(request)
            res = self.base.modules["document_retriever"].run(ctx, {})
            ev = res.output
            if isinstance(ev, dict):
                return ev.get("text")
        except Exception:
            pass
        return None

    @staticmethod
    def _annotate(
        result: ExecutionResult,
        tier_requested: str,
        tier_used: str,
        escalated: bool,
        reason: str | None,
        verdict: VerificationResult | str,
    ) -> None:
        if isinstance(verdict, str):
            verdict_meta = {"verifier_verdict": verdict}
        else:
            verdict_meta = verdict.to_metadata()
        result.escalated = escalated
        if reason:
            result.escalation_reason = reason
        for trace in result.traces:
            if trace.module == "small_model" or trace.module == "response_renderer":
                trace.metadata = {
                    **(trace.metadata or {}),
                    "tier_requested": tier_requested,
                    "tier_used": tier_used,
                    "tier_escalated": escalated,
                    "escalation_reason": reason,
                    **verdict_meta,
                }
