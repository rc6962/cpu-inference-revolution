# ADR-001: Adaptive CPU Cascade Serving Architecture

**Date:** 2026-09-07
**Status:** Proposed
**Branch:** phase-4-adaptive-cascade
**Baseline:** v0.3-adaptive-serving-baseline (3f6bf05)

## Context

Phase 3 demonstrated that Qwen2.5-1.5B Q4_K_M is approximately 2× faster than
Qwen2.5-3B Q4_K_M across both modular and forced benchmark modes on a single
Intel i7-11700T CPU core (median 40,415 ms vs 84,266 ms for modular; 72,091 ms
vs 139,026 ms for forced, per 30-case request loop).

However, the current 30-case benchmark scorer cannot distinguish quality between
models: 15 deterministic/extraction cases pass identically, and 15
retrieval/generation cases are scored N/A due to the weak scorer. The previous
1.5B-vs-3B comparison reported "quality indistinguishable" only under this
limitation — not that the models are semantically equivalent.

The core question: can we use 1.5B as the default tier, escalate to 3B only when
a structured verifier detects uncertainty or failure, and thereby achieve
3B-policy verified quality with fewer 3B calls, lower latency, and lower CPU
cost per successful task?

## Decision

Implement a deterministic two-tier adaptive cascade:

1. **Default tier:** 1.5B processes every request.
2. **Verifier:** A rule-based verifier inspects the 1.5B output against
   structured criteria (format compliance, factual grounding, confidence
   signals).
3. **Escalation:** Only when the verifier returns `needs_escalation` does the
   system re-run the request on 3B.
4. **No neural escalation:** The escalation decision is deterministic and
   inspectable — no learned router, no embedding similarity, no probability
   thresholds on model logits.

## Architecture

```
Request → 1.5B inference → Verifier → [pass/needs_escalation]
                                         ↓ (needs_escalation)
                                       3B inference → Verifier → result
```

### Escalation Rules (deterministic)

The verifier checks these conditions. If ANY are true, escalate to 3B:

| Rule | Category | Condition |
|------|----------|-----------|
| R1 | Format | Output fails expected format (e.g., margin not a percentage, invoice missing required fields) |
| R2 | Grounding | Retrieval output does not contain evidence from the selected source document |
| R3 | Length | Output is empty or below minimum token threshold for the category |
| R4 | Extraction | Invoice extractor returns fewer than 3 of 4 required fields |
| R5 | Calculation | Output does not match the deterministic calculator answer (when calculable) |

Rules R1–R4 are checked on the 1.5B output. R5 is checked by comparing 1.5B's
answer against the deterministic calculator — if they disagree, the deterministic
answer wins (no escalation needed, since it's deterministic).

### Verifier Contract

```python
class VerificationResult:
    verdict: str  # "verified" | "needs_escalation" | "needs_clarification" | "failed"
    reason: str | None
    checks_passed: list[str]
    checks_failed: list[str]
```

| Verdict | Meaning | Action |
|---------|---------|--------|
| `verified` | Output passes all category-specific checks | Return 1.5B result |
| `needs_escalation` | One or more escalation rules triggered | Re-run on 3B |
| `needs_clarification` | Request is ambiguous; no model can resolve it | Return clarification prompt |
| `failed` | Both tiers failed or request is out of scope | Return error |

### Trace Fields

Every trace will record:

| Field | Type | Description |
|-------|------|-------------|
| `tier_requested` | `str` | Which tier the policy selected ("1.5B" or "3B") |
| `tier_used` | `str` | Which tier actually produced the final output |
| `tier_escalated` | `bool` | Whether escalation from 1.5B to 3B occurred |
| `escalation_reason` | `str \| None` | Which verifier rule triggered escalation |
| `verifier_verdict` | `str` | The verifier's verdict on the final output |
| `verifier_checks_passed` | `list[str]` | Names of checks that passed |
| `verifier_checks_failed` | `list[str]` | Names of checks that failed |

### Model-Tier Configuration

```python
MODEL_TIERS = {
    "1.5B": {
        "path": "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "stem": "qwen2.5-1.5b-instruct-q4_k_m",
    },
    "3B": {
        "path": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
        "stem": "qwen2.5-3b-instruct-q4_k_m",
    },
}
```

Configuration is a plain dict loaded at runtime construction. No config file
format change. `CPU_INFERENCE_MODEL_PATH` remains the single-model override for
non-cascade modes.

## New Benchmark Suite (v1: 40–60 cases)

### Case Schema

```json
{
  "case_id": "cascade-001",
  "category": "calculation|extraction|retrieval|generation|ambiguous",
  "difficulty": "easy|medium|hard|ambiguous",
  "text": "Calculate the operating margin if revenue is 850000 and expenses are 612000",
  "attachments": [],
  "expected_route": "deterministic_calculation",
  "expected_verdict": "verified|needs_escalation|needs_clarification|failed",
  "expected_tier": "1.5B|3B|either",
  "expected_output_contains": ["28.00%"],
  "expected_source_id": null,
  "escalation_rules": ["R5"],
  "notes": "Deterministic — no escalation should occur"
}
```

### Case Distribution (target 50 cases)

| Category | Count | Difficulty | Expected Escalation Rate |
|----------|:-----:|------------|:------------------------:|
| calculation | 10 | easy (5), medium (3), hard (2) | ~0% (deterministic) |
| extraction | 10 | easy (5), medium (3), hard (2) | ~10% (format failures) |
| retrieval | 10 | easy (5), medium (3), hard (2) | ~20% (grounding failures) |
| generation | 10 | easy (3), medium (4), hard (3) | ~30% (quality variance) |
| ambiguous | 10 | ambiguous (10) | ~50% (clarification needed) |

### Case Design Principles

1. Every case has an explicit `expected_verdict` — the ground truth for whether
   escalation should occur.
2. "Easy" cases should always pass on 1.5B (verifier says `verified`).
3. "Hard" cases should always require escalation (verifier says
   `needs_escalation`).
4. "Ambiguous" cases test the `needs_clarification` path.
5. Cases are independent — no case depends on another's output.

## Benchmark Runner

### Three Conditions

| Condition | Description |
|-----------|-------------|
| `3b_default` | All requests go to 3B (current forced mode) |
| `1.5b_default` | All requests go to 1.5B (current forced mode) |
| `cascade` | 1.5B first, verifier decides, 3B on escalation |

### Metrics Collected Per Condition

| Metric | Description |
|--------|-------------|
| `total_wall_ms` | Request-loop wall time (same boundary as Phase 3) |
| `real_calls_1p5b` | Number of 1.5B model invocations |
| `real_calls_3b` | Number of 3B model invocations |
| `total_model_calls` | real_calls_1p5b + real_calls_3b |
| `escalations` | Number of requests escalated to 3B |
| `escalation_rate` | escalations / total cases |
| `verified_count` | Verifier verdict: verified |
| `needs_escalation_count` | Verifier verdict: needs_escalation |
| `needs_clarification_count` | Verifier verdict: needs_clarification |
| `failed_count` | Verifier verdict: failed |
| `quality_pass_rate` | Cases passing the scorer (same as Phase 3) |
| `cost_per_verified_task` | total_wall_ms / verified_count |

### Comparative Analysis

| Comparison | What It Answers |
|------------|----------------|
| cascade vs 3b_default wall time | How much latency does the cascade save? |
| cascade vs 3b_default 3B calls | How many 3B calls does the cascade avoid? |
| cascade vs 1.5b_default quality | Does escalation recover quality that 1.5B alone misses? |
| cascade escalation rate | What fraction of requests actually need 3B? |
| cascade cost_per_verified_task | Is the cascade cheaper per successful task? |

## Planned File List

| File | Purpose |
|------|---------|
| `docs/adr/ADR-001-adaptive-cascade.md` | This ADR |
| `data/benchmark_cases_cascade.jsonl` | 50-case cascade benchmark suite |
| `scripts/cascade_verifier.py` | Rule-based verifier implementation |
| `scripts/benchmark_cascade.py` | Cascade benchmark runner (3 conditions) |
| `scripts/score_cascade_quality.py` | Cascade-specific scorer |
| `runtime/cpu-cognitive-runtime-python/cognitive_runtime/cascade.py` | Cascade runtime wrapper |
| `tests/test_cascade.py` | Verifier and cascade runtime tests |
| `docs/phase-4-cascade-benchmark-report.md` | Study report |

## Acceptance Criteria for First Cascade Study

1. **All 50 cases run without error** in all 3 conditions.
2. **Verifier contract:** every case produces a verdict in
   {verified, needs_escalation, needs_clarification, failed}.
3. **Trace completeness:** every trace has tier_requested, tier_used,
   tier_escalated, escalation_reason, verifier_verdict, verifier_checks_passed,
   verifier_checks_failed.
4. **Escalation rate is between 5% and 60%.** If 0% or 100%, the verifier is
   broken or the cases are trivially easy/hard.
5. **3b_default quality ≥ cascade quality ≥ 1.5b_default quality** under the
   cascade scorer. If cascade quality < 1.5b_default, the verifier is harmful.
6. **cascade wall time < 3b_default wall time.** If not, the cascade adds no
   latency benefit.
7. **cascade 3B calls < 3b_default 3B calls.** The cascade must actually reduce
   3B usage.
8. **All traces use nested model_metrics** (same schema as Phase 3).
9. **No regressions to the existing 30-case control suite.** The old suite runs
   unchanged under all existing modes.
10. **28 existing tests pass.** New tests add coverage; no existing test breaks.

## Expected Risks

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Verifier too aggressive (escalates everything) | Medium | High | Tune thresholds on held-out cases; report escalation rate |
| Verifier too permissive (never escalates) | Medium | High | Include hard cases that provably need 3B; verify escalation occurs |
| Cascade latency > 3B latency (verification overhead + re-run) | Low | Medium | Measure verifier overhead separately; abort if >10% overhead |
| 1.5B output passes verifier but is semantically wrong | Medium | High | The weak scorer cannot detect this; document as known limitation |
| 50 cases too few for statistical significance | Medium | Low | This is v1; document sample-size limitations explicitly |
| Cascade runtime wrapper breaks existing modes | Low | High | Existing modes are untouched; cascade is additive |

## Rollback Plan

1. If the cascade verifier produces worse quality than 1.5B_default: delete
   `cascade.py`, `cascade_verifier.py`, and `benchmark_cascade.py`. The branch
   preserves all history; no main-branch changes exist.
2. If escalation rate is 0% or 100%: fix verifier thresholds and re-run. This
   is a tuning issue, not an architecture issue.
3. If cascade latency > 3B latency: profile verifier overhead. If verifier
   itself is the bottleneck, simplify rules. If re-run latency dominates, the
   cascade concept is not viable at this model size and the experiment fails
   gracefully.
4. In all cases, the v0.3-adaptive-serving-baseline tag is untouched. The branch
   can be abandoned without affecting main.

## Open Questions

1. **Scorer strength:** The current scorer cannot distinguish 1.5B from 3B
   quality on retrieval/generation cases. Should we invest in a stronger scorer
   before or after the cascade study? (Recommendation: after — the cascade study
   is the forcing function for scorer improvement.)
2. **Verifier calibration:** Should verifier thresholds be tuned on the same 50
   cases or on a held-out set? (Recommendation: same set for v1; split
   train/eval for v2 if v1 shows promise.)
3. **Streaming/TTFT:** If the cascade adds a second model call, the user sees
   latency only after the verifier decides. Should we stream the 1.5B result
   optimistically and discard it if escalation occurs? (Recommendation: not in
   v1 — keep the cascade synchronous and measurable.)
