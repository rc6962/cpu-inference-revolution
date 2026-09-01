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

## Interpreter note

Inside an activated virtual environment, use `python`. On Linux systems where `python` is unavailable, use `python3`.

## Run

### Fallback mode (no install)

**Linux / macOS:**
```bash
python3 example.py
python3 -m pytest -q
```

**Windows PowerShell:**
```powershell
python example.py
python -m pytest -q
```

### FTS5 retrieval mode

**Linux / macOS:**
```bash
python3 ../../data/init_db.py    # from repo root
python3 example.py
python3 -m pytest -q
```

**Windows PowerShell:**
```powershell
python ..\..\data\init_db.py     # from repo root
python example.py
python -m pytest -q
```

### Full inference mode

**Linux / macOS:**
```bash
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
mkdir -p ../../models
curl -L -o ../../models/qwen2.5-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
CPU_INFERENCE_MODEL_PATH=../../models/qwen2.5-3b-instruct-q4_k_m.gguf python3 example.py
```

**Windows PowerShell:**
```powershell
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
mkdir ..\..\models
curl -L -o ..\..\models\qwen2.5-3b-instruct-q4_k_m.gguf `
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
$env:CPU_INFERENCE_MODEL_PATH = "..\..\models\qwen2.5-3b-instruct-q4_k_m.gguf"
python example.py
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CPU_INFERENCE_MODEL_PATH` | No | `None` (demo mode) | Path to a GGUF model file |

When unset or pointing to a nonexistent file, SmallModel returns demo output automatically. The variable is read from the process environment. A `.env` file works only if it is loaded by the shell, launcher, or external tooling; the runtime does not load `.env` files itself.

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

Register it in `Runtime.__init__`, then select it from `Runtime.choose_graph`. The graph and telemetry code should not need to know whether the module uses a conventional Transformer, ONNX Runtime, a recurrent model, or a deterministic algorithm.

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
