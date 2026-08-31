# CPU Cognitive Runtime — Python

A modular CPU-native cognitive runtime with typed module contracts, conditional execution graphs, per-step telemetry, and exact-response caching.

**Working backends:**
- SmallModel: GGUF local inference via `llama-cpp-python` with chat completion
- DocumentRetriever: SQLite FTS5 full-text search with BM25 ranking

**Deterministic placeholders:**
- Calculator, InvoiceExtractor, Verifier, ResponseRenderer, RequestAnalyzer

## Prerequisites

- Python ≥ 3.10
- `pytest` (for tests)
- `sqlite3` (stdlib, no install needed)
- `llama-cpp-python` (optional, only for real inference)

The runtime works with zero external packages in fallback mode. All imports beyond the standard library are lazy-loaded.

## Run

### Fallback mode (no install)

```bash
python example.py
python -m pytest -q
```

### FTS5 retrieval mode

```bash
# Initialize the database (one-time, from repo root)
python ../../data/init_db.py

# Run with real retrieval
python example.py
python -m pytest -q
```

### Full inference mode

```bash
# Install llama-cpp-python (pre-built CPU wheel)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# Download model (from repo root)
mkdir -p ../../models
curl -L -o ../../models/qwen2.5-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"

# Set model path and run

# Bash / Linux / macOS:
CPU_INFERENCE_MODEL_PATH=../../models/qwen2.5-3b-instruct-q4_k_m.gguf python example.py

# PowerShell / Windows:
# $env:CPU_INFERENCE_MODEL_PATH = "E:\cpu-inference-revolution\models\qwen2.5-3b-instruct-q4_k_m.gguf"
# python example.py
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CPU_INFERENCE_MODEL_PATH` | No | `None` (demo mode) | Path to a GGUF model file |

When unset or pointing to a nonexistent file, SmallModel returns demo output automatically.

## Current module status

| Module | Backend | Status |
|--------|---------|--------|
| RequestAnalyzer | Regex rules | Deterministic |
| Calculator | Regex extraction | Deterministic |
| DocumentRetriever | SQLite FTS5 | Real retrieval |
| SmallModel | llama-cpp-python GGUF | Real inference |
| InvoiceExtractor | Regex extraction | Deterministic |
| Verifier | Schema checks | Deterministic |
| ResponseRenderer | Pass-through | Deterministic |

## Replace a demo module

Implement the same interface:

```python
class MyModel:
    name = "my_model"
    residency = Residency.WARM

    def run(self, context, inputs):
        return ModuleResult(
            module=self.name,
            status="success",
            output={"answer": "..."},
            confidence=0.9,
        )
```

Register it in `Runtime.__init__`, then select it from `Runtime.choose_graph`. The graph and telemetry code does not need to know whether the module uses a Transformer, ONNX Runtime, a recurrent model, or a deterministic algorithm.

## Deliberate limitations

This is a research starting point, not a production server. Current limitations:

- No authentication, rate limiting, or network serving
- No persistent session state (in-memory cache only)
- No streaming inference
- InvoiceExtractor handles only vendor/tax/total fields
- DocumentRetriever uses keyword matching, not semantic search
- SmallModel inference is ~13s per request on a 1.4GHz CPU (hardware-limited)
- No sandboxed tool execution
- No production-grade safety policy
