#!/usr/bin/env python3
"""Three-mode benchmark orchestrator.

Runs Mode A (fallback), Mode B (modular), Mode C (forced single-model)
against the same 30-case dataset from data/benchmark_cases.jsonl.

No runtime.py changes — ForcedModelRuntime and ForcedSmallModel are
benchmark-only subclasses that inject task-aware system prompts via
context.values.

Usage:
    # All three modes (requires model for B and C):
    python scripts/benchmark_all_modes.py

    # Fallback only:
    python scripts/benchmark_all_modes.py --mode fallback

    # Modular only:
    python scripts/benchmark_all_modes.py --mode modular

    # Forced only:
    python scripts/benchmark_all_modes.py --mode forced
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

# ── Setup paths ──
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "runtime" / "cpu-cognitive-runtime-python"
sys.path.insert(0, str(RUNTIME_DIR))

from cognitive_runtime.runtime import (  # noqa: E402
    ExecutionGraph,
    ExecutionContext,
    Request,
    Runtime,
    Step,
    trace_to_dict,
)

CASES_PATH = REPO_ROOT / "data" / "benchmark_cases.jsonl"


# ── Load cases ──
def load_cases() -> list[dict]:
    with open(CASES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Forced-mode components (script-only, no runtime.py change) ──

TASK_SYSTEM_PROMPTS = {
    "calculation": "You are a calculator. Compute the exact numeric answer. Return ONLY the number with no explanation.",
    "extraction": 'You are an invoice parser. Extract vendor, tax, and total from the text. Return ONLY valid JSON: {"vendor": "...", "tax": N, "total": N}',
    "retrieval": "Answer the following question based on your knowledge. Be concise.",
    "generation": "You are a professional writing assistant. Rewrite the given text to sound more professional. Return ONLY the rewritten text.",
}


class ForcedSmallModel:
    """Benchmark-only SmallModel wrapper that injects task-aware system prompts.

    Replaces the real SmallModel in ForcedModelRuntime's module registry.
    Reads _forced_system_prompt from context.values if present.
    Falls back to normal SmallModel behavior if not.
    """
    name = "small_model"
    residency = None  # not used in benchmark

    def __init__(self, real_small_model):
        self._real = real_small_model

    def run(self, context, inputs):
        # Ensure real model is loaded
        self._real._load_model()
        forced_sys = context.values.get("_forced_system_prompt")
        if forced_sys and self._real._llm is not None:
            user_text = inputs.get("prompt", context.request.text)
            messages = [
                {"role": "system", "content": forced_sys},
                {"role": "user", "content": user_text},
            ]
            try:
                result = self._real._llm.create_chat_completion(
                    messages=messages, max_tokens=256, temperature=0.0,
                )
                text = result["choices"][0]["message"]["content"].strip()
                if not text:
                    text = f"Demo response for: {context.request.text}"
                from cognitive_runtime.runtime import ModuleResult
                return ModuleResult(self.name, "success", text, 0.7)
            except Exception as exc:
                from cognitive_runtime.runtime import ModuleResult
                return ModuleResult(
                    self.name, "success",
                    f"Demo response for: {context.request.text}",
                    0.5, warnings=[f"LLM inference failed: {exc}"],
                )
        # Fallback: use real SmallModel normally
        return self._real.run(context, inputs)


class ForcedModelRuntime(Runtime):
    """Benchmark-only: routes every case through SmallModel with task-aware prompts.

    choose_graph() always returns a simple generate→render graph.
    execute_forced() injects the task-specific system prompt.
    """
    def choose_graph(self, analysis):
        return ExecutionGraph([
            Step("generate", "small_model", output_key="answer"),
            Step("render", "response_renderer", ("answer",), "response"),
        ], "forced_single_model")

    def execute_forced(self, request, category):
        """Execute with task-aware system prompt injection."""
        context = ExecutionContext(request)
        context.values["_forced_system_prompt"] = TASK_SYSTEM_PROMPTS.get(category, "")
        analysis = self.analyze(request)
        graph = self.choose_graph(analysis)
        return graph.run(context, self.modules)


# ── Benchmark runner ──

def run_benchmark(runtime, cases, mode, model_loaded=False):
    """Run all cases through the runtime, return results with timing."""
    results = []
    model_invoke_count = 0
    total_wall_ms = 0

    for case in cases:
        req = Request(
            request_id=f"bench-{mode}-{case['id']}",
            session_id="bench",
            text=case["input"],
        )

        t0 = time.perf_counter()

        if mode == "forced":
            result = runtime.execute_forced(req, case["category"])
        else:
            result = runtime.execute(req)

        wall_ms = (time.perf_counter() - t0) * 1000
        total_wall_ms += wall_ms

        # Count model invocations and capture metadata
        small_model_calls = 0
        real_llm_inferences = 0
        fallback_responses = 0
        verification_attempted = False
        verification_status = "not_attempted"
        retrieved_source_id = None
        retrieval_attempted = False
        retrieval_status = "not_attempted"
        token_time = {}

        for trace in result.traces:
            if trace.module == "small_model":
                small_model_calls += 1
                meta = trace.metadata
                if meta.get("fallback_used", False):
                    fallback_responses += 1
                else:
                    real_llm_inferences += 1
                    token_time = {
                        "input_tokens": meta.get("input_tokens", 0),
                        "evidence_tokens": meta.get("evidence_tokens", 0),
                        "output_tokens": meta.get("output_tokens", 0),
                        "generation_time_ms": meta.get("generation_time_ms", 0),
                        "stop_reason": meta.get("stop_reason", "unknown"),
                        "model_name": meta.get("model_name", "unknown"),
                    }
            if trace.module == "verifier":
                verification_attempted = True
                verification_status = trace.status
            if trace.module == "document_retriever":
                retrieval_attempted = True
                retrieval_status = trace.status
                # Extract source_id from output_summary using regex
                import re
                m = re.search(r"source_id['\"]?\s*:\s*['\"]([^'\"]+)", trace.output_summary)
                if m:
                    retrieved_source_id = m.group(1)

        # Extract per-step timings
        steps = {}
        traces_data = trace_to_dict(result)["steps"] if result.traces else []
        for trace in traces_data:
            steps[trace["module"]] = round(trace["cpu_ms"], 1)

        results.append({
            "case": case,
            "output": result.output or "",
            "route": result.route,
            "status": result.status,
            "wall_ms": round(wall_ms, 1),
            "steps": steps,
            "traces": traces_data,
            "small_model_calls": small_model_calls,
            "real_llm_inferences": real_llm_inferences,
            "fallback_responses": fallback_responses,
            "verification_attempted": verification_attempted,
            "verification_status": verification_status,
            "retrieved_source_id": retrieved_source_id,
            "retrieval_attempted": retrieval_attempted,
            "retrieval_status": retrieval_status,
            "token_time": token_time,
        })

        # Clear cache between requests for clean timing
        runtime.cache.clear()

    return {
        "mode": mode,
        "results": results,
        "model_invoke_count": model_invoke_count,
        "total_wall_ms": round(total_wall_ms, 1),
        "avg_wall_ms": round(total_wall_ms / len(cases), 1),
        "case_count": len(cases),
    }


def print_mode_summary(benchmark: dict, model_loaded: bool):
    """Print a concise summary table for one mode."""
    mode = benchmark["mode"]
    print(f"\n{'='*70}")
    print(f"Mode: {mode.upper()}")
    print(f"Cases: {benchmark['case_count']}, Model invoked: {benchmark['model_invoke_count']}x")
    print(f"Total wall: {benchmark['total_wall_ms']:.0f} ms, Avg: {benchmark['avg_wall_ms']:.0f} ms")
    print(f"{'='*70}")

    # Per-category breakdown
    categories = {}
    for r in benchmark["results"]:
        cat = r["case"]["category"]
        if cat not in categories:
            categories[cat] = {"wall_times": [], "model_steps": [], "outputs": []}
        categories[cat]["wall_times"].append(r["wall_ms"])
        if "small_model" in r["steps"]:
            categories[cat]["model_steps"].append(r["steps"]["small_model"])
        categories[cat]["outputs"].append(r["output"][:80])

    print(f"\n{'Category':<15} {'Count':>5} {'Avg Wall':>10} {'Avg Model':>10} {'Model?':>7}")
    print("-" * 55)
    for cat, data in categories.items():
        avg_wall = statistics.mean(data["wall_times"])
        avg_model = statistics.mean(data["model_steps"]) if data["model_steps"] else 0
        model_used = "Yes" if data["model_steps"] else "No"
        print(f"{cat:<15} {len(data['wall_times']):>5} {avg_wall:>9.0f}ms {avg_model:>9.0f}ms {model_used:>7}")

    # Sample outputs
    print(f"\nSample outputs:")
    for r in benchmark["results"][:3]:
        print(f"  {r['case']['id']}: {r['output'][:100]}")


def main():
    parser = argparse.ArgumentParser(description="Three-mode benchmark")
    parser.add_argument("--mode", choices=["fallback", "modular", "forced", "all"], default="all")
    args = parser.parse_args()

    model_path = os.environ.get("CPU_INFERENCE_MODEL_PATH")
    model_loaded = model_path is not None and Path(model_path).exists()
    db_path = str(REPO_ROOT / "data" / "knowledge.db")
    db_exists = Path(db_path).is_file()

    print("=== Three-Mode Benchmark ===")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Model: {Path(model_path).name if model_loaded else '(none)'}")
    print(f"DB: {'exists' if db_exists else 'missing'}")
    print(f"Cases: {CASES_PATH}")

    cases = load_cases()
    print(f"Loaded: {len(cases)} cases")

    all_benchmarks = []

    # ── Mode A: Fallback ──
    if args.mode in ("fallback", "all"):
        print("\n--- Mode A: Fallback ---")
        runtime = Runtime()  # No model, no DB changes
        benchmark = run_benchmark(runtime, cases, "fallback", model_loaded=False)
        print_mode_summary(benchmark, model_loaded=False)
        all_benchmarks.append(benchmark)
        # Save results
        with open(REPO_ROOT / "results_mode_a.json", "w") as f:
            json.dump(benchmark, f, indent=2)
        print(f"Saved: results_mode_a.json")

    # ── Mode B: Modular real-model ──
    if args.mode in ("modular", "all") and model_loaded:
        print("\n--- Mode B: Modular real-model ---")
        runtime = Runtime()  # Uses real model for small_rag/small_direct only
        # Force model load
        req = Request(request_id="warmup", session_id="bench", text="warmup")
        runtime.execute(req)
        benchmark = run_benchmark(runtime, cases, "modular", model_loaded=True)
        print_mode_summary(benchmark, model_loaded=True)
        all_benchmarks.append(benchmark)
        with open(REPO_ROOT / "results_mode_b.json", "w") as f:
            json.dump(benchmark, f, indent=2)
        print(f"Saved: results_mode_b.json")
    elif args.mode in ("modular", "all"):
        print("\n--- Mode B: SKIPPED (no model configured) ---")

    # ── Mode C: Forced single-model ──
    if args.mode in ("forced", "all") and model_loaded:
        print("\n--- Mode C: Forced single-model ---")
        runtime = ForcedModelRuntime()
        # Replace SmallModel with ForcedSmallModel
        runtime.modules["small_model"] = ForcedSmallModel(runtime.modules["small_model"])
        # Force model load
        req = Request(request_id="warmup", session_id="bench", text="warmup")
        runtime.execute_forced(req, "generation")
        benchmark = run_benchmark(runtime, cases, "forced", model_loaded=True)
        print_mode_summary(benchmark, model_loaded=True)
        all_benchmarks.append(benchmark)
        with open(REPO_ROOT / "results_mode_c.json", "w") as f:
            json.dump(benchmark, f, indent=2)
        print(f"Saved: results_mode_c.json")
    elif args.mode in ("forced", "all"):
        print("\n--- Mode C: SKIPPED (no model configured) ---")

    # ── Summary ──
    if len(all_benchmarks) > 1:
        print(f"\n{'='*70}")
        print("CROSS-MODE COMPARISON")
        print(f"{'='*70}")
        print(f"\n{'Mode':<12} {'Cases':>5} {'Model Used':>10} {'Total Wall':>12} {'Avg Wall':>10}")
        print("-" * 55)
        for b in all_benchmarks:
            print(f"{b['mode']:<12} {b['case_count']:>5} {b['model_invoke_count']:>10} {b['total_wall_ms']:>11.0f}ms {b['avg_wall_ms']:>9.0f}ms")


if __name__ == "__main__":
    main()
