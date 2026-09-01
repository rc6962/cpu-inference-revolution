#!/usr/bin/env python3
"""Run 1.5B vs 3B model comparison: 5 iterations each of Mode B and Mode C."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_BASE = REPO / "results" / "model-comparison" / "dc51d19"
VENV_PYTHON = str(REPO / ".venv" / "Scripts" / "python.exe")
BENCHMARK_SCRIPT = str(REPO / "scripts" / "benchmark_all_modes.py")
DB_INIT = str(REPO / "data" / "init_db.py")

MODELS = {
    "qwen2.5-1.5b-q4_k_m": str(REPO / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    "qwen2.5-3b-q4_k_m": str(REPO / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf"),
}

for model_name, model_path in MODELS.items():
    model_dir = RESULTS_BASE / model_name
    model_dir.mkdir(parents=True, exist_ok=True)

    # Reinitialize DB before each model study
    print(f"\n=== Reinitializing DB for {model_name} ===", flush=True)
    subprocess.run([VENV_PYTHON, DB_INIT], cwd=str(REPO), capture_output=True)

    # Warmup: 2 passes per model
    for w in range(1, 3):
        for mode in ["modular", "forced"]:
            print(f"  Warmup {w}/2: {mode}...", end=" ", flush=True)
            env = os.environ.copy()
            env["CPU_INFERENCE_MODEL_PATH"] = model_path
            subprocess.run(
                [VENV_PYTHON, BENCHMARK_SCRIPT, "--mode", mode],
                env=env, capture_output=True, timeout=600, cwd=str(REPO),
            )
            print("done", flush=True)

    # Measured runs: 5 iterations of each mode
    for mode in ["modular", "forced"]:
        mode_letter = {"modular": "b", "forced": "c"}[mode]
        for i in range(1, 6):
            run_id = f"mode_{mode_letter}_run_{i:02d}"
            out_file = model_dir / f"{run_id}.json"

            print(f"  Running {model_name} {run_id}...", end=" ", flush=True)
            env = os.environ.copy()
            env["CPU_INFERENCE_MODEL_PATH"] = model_path
            subprocess.run(
                [VENV_PYTHON, BENCHMARK_SCRIPT, "--mode", mode],
                env=env, capture_output=True, timeout=600, cwd=str(REPO),
            )

            canonical = REPO / f"results_mode_{mode_letter}.json"
            if canonical.exists():
                shutil.copy2(canonical, out_file)
                with open(out_file) as f:
                    data = json.load(f)
                print(f"{data['total_wall_ms']:.0f} ms", flush=True)
            else:
                print("FAILED", flush=True)

print("\nDone.")
