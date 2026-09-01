#!/usr/bin/env python3
"""Run 5 iterations of each benchmark mode, saving raw results."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO / "results" / "repeated-runs" / "9a8c5d7"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = str(REPO / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf")
VENV_PYTHON = str(REPO / ".venv" / "Scripts" / "python.exe")
BENCHMARK_SCRIPT = str(REPO / "scripts" / "benchmark_all_modes.py")

for mode, count in [("fallback", 5), ("modular", 5), ("forced", 5)]:
    mode_letter = {"fallback": "a", "modular": "b", "forced": "c"}[mode]
    for i in range(1, count + 1):
        run_id = f"mode_{mode_letter}_run_{i:02d}"
        out_file = RESULTS_DIR / f"{run_id}.json"
        
        env = os.environ.copy()
        if mode in ("modular", "forced"):
            env["CPU_INFERENCE_MODEL_PATH"] = MODEL_PATH
        else:
            env.pop("CPU_INFERENCE_MODEL_PATH", None)
        
        print(f"Running {run_id}...", flush=True)
        result = subprocess.run(
            [VENV_PYTHON, BENCHMARK_SCRIPT, "--mode", mode],
            env=env, capture_output=True, text=True, timeout=600,
            cwd=str(REPO),
        )
        
        # Copy the canonical results file to the run-specific file
        canonical = REPO / f"results_mode_{mode_letter}.json"
        if canonical.exists():
            shutil.copy2(canonical, out_file)
            with open(out_file) as f:
                data = json.load(f)
            wall = data.get("total_wall_ms", 0)
            print(f"  {run_id}: {wall:.0f} ms wall time", flush=True)
        else:
            print(f"  {run_id}: FAILED - no results file", flush=True)

print("\nDone. All runs saved to:", RESULTS_DIR)
