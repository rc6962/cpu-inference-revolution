#!/usr/bin/env python3
"""Reproducible benchmark for the CPU cognitive runtime.

Measures per-route latency with unique prompts (no cache contamination).
Reports environment, model configuration, and timings.

Usage:
    python scripts/benchmark_runtime.py
    CPU_INFERENCE_MODEL_PATH=/path/to/model.gguf python scripts/benchmark_runtime.py
"""
from __future__ import annotations

import os
import re
import statistics
import sys
import time
from pathlib import Path

# ── Ensure the runtime package is importable ──
RUNTIME_DIR = Path(__file__).resolve().parent.parent / "runtime" / "cpu-cognitive-runtime-python"
sys.path.insert(0, str(RUNTIME_DIR))

from cognitive_runtime.runtime import Request, Runtime, trace_to_dict  # noqa: E402

# ── Unique prompts per route (3 each, no repeats) ──
PROMPTS = {
    "small_direct": [
        "Rewrite to sound professional: The meeting went okay.",
        "Make formal: We need the report by Friday.",
        "Improve clarity: The project has some issues.",
    ],
    "small_rag": [
        "According to the policy, how many days notice are required?",
        "What does the contract say about termination?",
        "How many sick days does the handbook allow?",
    ],
    "deterministic_calculation": [
        "Operating margin if revenue 850000 expenses 612000?",
        "Profit margin if revenue 500000 costs 375000?",
        "Margin percentage if sales 1200000 expenses 960000?",
    ],
    "invoice_extraction": [
        "Extract invoice: Vendor Acme, Tax 45, Total 245",
        "Extract invoice: Vendor Beta Inc, Tax 12.50, Total 62.50",
        "Extract invoice: Vendor Gamma Co, Tax 88, Total 488",
    ],
}


def get_ram() -> tuple[float, float]:
    """Return (total_gb, free_gb). Cross-platform: Windows, Linux, macOS."""
    import os
    import platform
    import subprocess

    system = platform.system()

    # Windows: PowerShell
    if system == "Windows":
        try:
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "$o=Get-CimInstance Win32_OperatingSystem;"
                 "Write-Host ([math]::Round($o.TotalVisibleMemorySize/1MB,2));"
                 "Write-Host ([math]::Round($o.FreePhysicalMemory/1MB,2))"],
                text=True, timeout=5,
            )
            lines = out.strip().split()
            return float(lines[0]), float(lines[1])
        except Exception:
            pass

    # Linux: /proc/meminfo
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])  # kB
            total_kb = info.get("MemTotal", 0)
            free_kb = info.get("MemAvailable", info.get("MemFree", 0))
            return round(total_kb / 1048576, 2), round(free_kb / 1048576, 2)
        except Exception:
            pass

    # macOS: sysctl
    if system == "Darwin":
        try:
            total_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5
            ).strip())
            # Free memory: use vm_stat
            vm = subprocess.check_output(["vm_stat"], text=True, timeout=5)
            page_size = 4096  # default
            for line in vm.splitlines():
                if "page size of" in line.lower():
                    page_size = int(line.split()[-2])
                    break
            free_pages = 0
            for line in vm.splitlines():
                if "Pages free" in line:
                    free_pages = int(line.split()[-1].rstrip("."))
                    break
            free_bytes = free_pages * page_size
            return round(total_bytes / (1024**3), 2), round(free_bytes / (1024**3), 2)
        except Exception:
            pass

    return 0.0, 0.0


def bench_route(runtime: Runtime, route: str, prompts: list[str]) -> dict:
    """Run 3 unique prompts through a route, return timing stats."""
    times = []
    model_times = []
    for p in prompts:
        req = Request(request_id=f"bench-{route}-{hash(p)}", session_id="bench", text=p)
        t0 = time.perf_counter()
        result = runtime.execute(req)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(round(elapsed, 1))
        # Find SmallModel step time
        for trace in result.traces:
            if trace.module == "small_model":
                model_times.append(round(trace.cpu_ms, 1))
    return {
        "min_ms": min(times),
        "avg_ms": round(statistics.mean(times), 1),
        "max_ms": max(times),
        "model_step_avg_ms": round(statistics.mean(model_times), 1) if model_times else 0,
    }


def main() -> None:
    model_path = os.environ.get("CPU_INFERENCE_MODEL_PATH")
    model_name = Path(model_path).name if model_path else None
    db_path = str(RUNTIME_DIR.parent.parent / "data" / "knowledge.db")
    db_exists = Path(db_path).is_file()

    print("=== CPU Cognitive Runtime Benchmark ===")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Model: {model_name or '(none)'}")
    print(f"DB: {'exists' if db_exists else 'missing'}")
    print(f"CWD: {Path.cwd()}")
    print()

    ram_before = get_ram()

    # Cold load
    t0 = time.perf_counter()
    runtime = Runtime()
    # Force SmallModel load if model configured
    if model_path:
        from cognitive_runtime.runtime import ExecutionContext, Analysis, Constraints
        req = Request(request_id="cold-load", session_id="bench", text="warm up")
        runtime.execute(req)
    cold_ms = round((time.perf_counter() - t0) * 1000, 1)

    ram_after = get_ram()

    results = {}
    for route, prompts in PROMPTS.items():
        results[route] = bench_route(runtime, route, prompts)

    ram_final = get_ram()

    print(f"{'Route':<30} {'Min':>8} {'Avg':>8} {'Max':>8} {'Model':>8}")
    print("-" * 62)
    for route, data in results.items():
        print(f"{route:<30} {data['min_ms']:>7.1f} {data['avg_ms']:>7.1f} {data['max_ms']:>7.1f} {data['model_step_avg_ms']:>7.1f}")
    print("-" * 62)
    print(f"{'cold_load':<30} {'':>8} {cold_ms:>7.1f} {'':>8} {'':>8}")
    print()
    print(f"RAM before: {ram_before[1]:.2f} GB free")
    print(f"RAM after:  {ram_after[1]:.2f} GB free")
    print(f"RAM used:   {ram_before[1] - ram_after[1]:.2f} GB")
    print()
    print("All times in milliseconds. Model column = SmallModel step only.")


if __name__ == "__main__":
    main()
