# CPU Inference Revolution

A research project exploring CPU-native cognitive serving: redesigning model architecture and inference hosting around CPU control flow, large DRAM, local NVMe, persistent state, retrieval, deterministic tools, modular specialists, and adaptive execution.

## Contents

- `docs/cpu-native-ai-conversation-reference.md` — organized reference of the complete design conversation.
- `docs/cpu-first-llm-starting-guide.md` — ordered implementation and testing guide.
- `docs/cpu-native-cognitive-serving-blueprint.md` — detailed architecture, model candidates, runtime design, and 90-day plan.
- `docs/cpu-native-tonight-lab-plan.md` — short preliminary research and experimentation plan.
- `runtime/cpu-cognitive-runtime-python/` — Python runtime with typed module contracts, execution graphs, routing, verification, traces, caching, and tests.
- `data/seed.jsonl` — seed documents for FTS5 retrieval testing.
- `data/init_db.py` — initializes the SQLite FTS5 knowledge base.
- `scripts/benchmark_runtime.py` — reproducible benchmark with unique prompts per route.

## Current thesis

> AI requests should be planned, routed, remembered, retrieved, computed, verified, and rendered—not simply pushed through one dense model until it emits text.

The near-term objective is not to replace GPUs for every large-model workload. It is to determine whether a CPU-centered system can complete selected private, stateful, retrieval-heavy, or structured business tasks with lower total cost per verified successful task.

## What's implemented

The runtime includes three working backends beyond the original deterministic placeholders:

- **SmallModel** — GGUF-backed local inference via `llama-cpp-python` with chat completion, lazy loading, and automatic fallback to demo output when no model is configured.
- **DocumentRetriever** — SQLite FTS5 full-text search with porter stemming, stop-word filtering, and BM25 ranking. Falls back to synthetic evidence when the database is missing.
- **RequestAnalyzer** — routes invoice prompts from text-only input using compound keyword detection.

All other modules (Calculator, InvoiceExtractor, Verifier, ResponseRenderer) remain deterministic regex-based implementations.

## Quick start

### Fallback mode (no install required)

Runs with deterministic placeholder modules. No model download, no database.

```bash
cd runtime/cpu-cognitive-runtime-python
python example.py
python -m pytest -q
```

### FTS5 retrieval mode

Adds real document retrieval from a local SQLite database. Still no model needed.

```bash
# Initialize the knowledge base (one-time, from repo root)
python data/init_db.py

# Run with real retrieval
cd runtime/cpu-cognitive-runtime-python
python example.py
python -m pytest -q
```

### Full local-LLM mode

Adds real CPU inference via a quantized GGUF model.

```bash
# 1. Install llama-cpp-python (pre-built CPU wheel)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 2. Download the model (~2 GB)
mkdir -p models
curl -L -o models/qwen2.5-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"

# 3. Initialize the knowledge base
python data/init_db.py

# 4. Set the model path and run
cd runtime/cpu-cognitive-runtime-python

# Bash / Linux / macOS:
CPU_INFERENCE_MODEL_PATH=../../models/qwen2.5-3b-instruct-q4_k_m.gguf python example.py

# PowerShell / Windows:
# $env:CPU_INFERENCE_MODEL_PATH = "E:\cpu-inference-revolution\models\qwen2.5-3b-instruct-q4_k_m.gguf"
# python example.py
```

## Architecture

Each request flows through: analyze → route → retrieve → compute → verify → render.

The execution graph is conditional — only the modules needed for the selected route are invoked. Per-step CPU timing and trace output are recorded automatically.

| Module | Backend | Trigger route |
|--------|---------|---------------|
| RequestAnalyzer | Regex rules | All requests |
| Calculator | Regex extraction | `deterministic_calculation` |
| DocumentRetriever | SQLite FTS5 | `small_rag` |
| SmallModel | llama-cpp-python GGUF | `small_rag`, `small_direct` |
| InvoiceExtractor | Regex extraction | `invoice_extraction` |
| Verifier | Schema checks | `small_rag`, `invoice_extraction` |
| ResponseRenderer | Pass-through | All routes |

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CPU_INFERENCE_MODEL_PATH` | No | `None` (demo mode) | Path to a GGUF model file |

When unset or pointing to a nonexistent file, SmallModel returns demo output automatically. The variable can be set in the shell, in PowerShell, or exported in a `.env` file loaded by your shell profile.

## Generated files (not committed)

| File | How created | Size |
|------|-------------|------|
| `data/knowledge.db` | `python data/init_db.py` | ~28 KB |
| `models/*.gguf` | Manual download from HuggingFace | ~2 GB |

These are listed in `.gitignore` and must be recreated after a fresh clone.

## Hardware and benchmarks

Measured on Intel i7-11700T (8C/16T @ 1.4GHz), 15.45 GB RAM, Windows 11 Pro:

| Metric | Fallback | With Qwen2.5-3B Q4_K_M |
|--------|----------|------------------------|
| Cold load | <1 ms | ~10 s |
| Small direct inference | <1 ms | ~13 s |
| Small RAG inference | <1 ms | ~13 s |
| Deterministic calculation | <1 ms | <1 ms |
| Cache hit | <1 ms | <1 ms |
| RAM usage | 0 GB | ~3.1 GB |

These are single-machine measurements. Your results will vary with CPU, RAM, model quantization, and background load. Run `python scripts/benchmark_runtime.py` to reproduce on your hardware.

## Research discipline

Keep a fixed benchmark, record CPU/RAM/storage details, separate cold-start from warm inference, run routing in shadow mode before activating it, and measure CPU milliseconds per verified successful task rather than tokens per second alone.

## Status

Research prototype. Two of seven modules now use real backends (SmallModel, DocumentRetriever). Five modules remain deterministic placeholders. Not production software.
