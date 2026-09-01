"""Dependency-light CPU-native cognitive runtime skeleton.

This module intentionally uses deterministic demo modules. Replace them with
real model adapters behind the same interfaces after the graph and telemetry
behavior are validated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import os
import re
from pathlib import Path
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol


class Residency(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass(frozen=True)
class Constraints:
    latency_budget_ms: int = 3_000
    memory_budget_mb: int = 4_096
    quality_target: float = 0.95


@dataclass(frozen=True)
class Request:
    request_id: str
    session_id: str
    text: str
    attachments: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    constraints: Constraints = field(default_factory=Constraints)


@dataclass
class Analysis:
    task_type: str
    risk_level: str
    difficulty_band: str
    requires_retrieval: bool
    requires_tools: bool
    output_format: str
    recommended_route: str
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    deterministic_operation: Optional[str] = None


@dataclass
class ModuleResult:
    module: str
    status: str
    output: Any = None
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepTrace:
    step_id: str
    module: str
    status: str
    cpu_ms: float
    output_summary: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    request_id: str
    status: str
    output: Any
    route: str
    traces: list[StepTrace]
    escalated: bool = False
    escalation_reason: Optional[str] = None


@dataclass
class ExecutionContext:
    request: Request
    analysis: Optional[Analysis] = None
    state: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    traces: list[StepTrace] = field(default_factory=list)


class Module(Protocol):
    name: str
    residency: Residency

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        ...


class BaseModule:
    name = "base"
    residency = Residency.HOT

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        raise NotImplementedError


class RequestAnalyzer(BaseModule):
    name = "request_analyzer"

    _calc = re.compile(r"\b(?:calculate|compute|what is|percentage|margin|convert)\b", re.I)
    _invoice = re.compile(r"\b(?:invoice|receipt|vendor|subtotal|tax|due date)\b", re.I)
    _retrieval = re.compile(r"\b(?:according to|policy|policies|contract|documents?|lookup|find|what does|handbook|sick|vacation|probation|resignation|onboarding|benefits|notice|requirements?|allow)\b", re.I)
    _code = re.compile(r"```|\b(?:python|javascript|sql|api|function|stack trace|bug|compile)\b", re.I)
    _high_risk = re.compile(r"\b(?:medical|diagnos|dosage|legal advice|tax filing|investment|password|credential)\b", re.I)

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text.strip()
        lowered = text.lower()
        reasons: list[str] = []
        risk = "high" if self._high_risk.search(text) else "low"

        _invoice_fields = re.compile(r"\b(?:vendor|subtotal|total)\b", re.I)
        if self._invoice.search(text) and (context.request.attachments or _invoice_fields.search(text)):
            task = "structured_extraction"
            route = "invoice_extraction"
            output_format = "strict_json"
            requires_tools = True
            reasons.append("TASK_INVOICE_EXTRACTION")
        elif self._calc.search(text) and re.search(r"\d", text):
            task = "calculation"
            route = "deterministic_calculation"
            output_format = "text"
            requires_tools = True
            reasons.append("RULE_DETERMINISTIC_CALCULATION")
        elif self._code.search(text):
            task = "coding"
            route = "specialist"
            output_format = "text"
            requires_tools = False
            reasons.append("TASK_CODING")
        elif self._retrieval.search(text) or context.request.attachments:
            task = "retrieval_qa"
            route = "small_rag"
            output_format = "text"
            requires_tools = False
            reasons.append("RULE_RETRIEVAL_REQUIRED")
        else:
            task = "small_direct"
            route = "small_direct"
            output_format = "text"
            requires_tools = False
            reasons.append("TASK_GENERIC_DIRECT")

        word_count = len(text.split())
        difficulty = "easy" if word_count < 80 else "moderate" if word_count < 400 else "hard"
        if task in {"coding", "structured_extraction"}:
            difficulty = "moderate"
        if risk == "high":
            difficulty = "hard"
            reasons.append("RISK_REQUIRES_ESCALATION_POLICY")

        analysis = Analysis(
            task_type=task,
            risk_level=risk,
            difficulty_band=difficulty,
            requires_retrieval=task == "retrieval_qa",
            requires_tools=requires_tools,
            output_format=output_format,
            recommended_route=route,
            confidence=0.90 if task != "small_direct" else 0.70,
            reason_codes=reasons,
        )
        return ModuleResult(self.name, "success", analysis, analysis.confidence)


class Calculator(BaseModule):
    name = "calculator"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text
        numbers = [Decimal(x.replace(",", "")) for x in re.findall(r"\$?\d[\d,]*(?:\.\d+)?", text)]
        if len(numbers) < 2:
            return ModuleResult(self.name, "failed", warnings=["not_enough_numbers"])

        if "margin" in text.lower() and len(numbers) >= 2:
            revenue, expenses = numbers[0], numbers[1]
            result = (revenue - expenses) / revenue
            formatted = f"{result * 100:.2f}%"
            expression = f"({revenue} - {expenses}) / {revenue}"
        elif "/" in text and len(numbers) >= 2:
            result = numbers[0] / numbers[1]
            formatted = f"{result:.6f}"
            expression = f"{numbers[0]} / {numbers[1]}"
        else:
            result = sum(numbers)
            formatted = f"{result:.2f}"
            expression = " + ".join(str(n) for n in numbers)

        return ModuleResult(self.name, "success", {
            "expression": expression,
            "result": float(result),
            "formatted_result": formatted,
        })


class DocumentRetriever(BaseModule):
    name = "document_retriever"
    residency = Residency.WARM

    # Generic question terms that should not drive ranking
    _QUESTION_TERMS = re.compile(
        r"\b(?:how|what|when|where|why|who|which|does|do|is|are|was|were|can|could|would|should|may|might|will|shall|the|a|an|to|of|for|in|on|with|by|from|this|that|it|and|or|not)\b",
        re.I,
    )

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(
            Path(__file__).parent.parent.parent.parent / "data" / "knowledge.db"
        )

    def _db_exists(self) -> bool:
        return Path(self._db_path).is_file()

    _STOP_WORDS = re.compile(
        r"\b(?:according|to|the|how|many|what|does|is|are|was|were|a|an|in|on|of|for|with|by|from|this|that|it|and|or|not|be|been|being|have|has|had|do|does|did|will|would|shall|should|may|might|can|could)\b",
        re.I,
    )

    def _normalize_query(self, query_text: str) -> str:
        """Strip stop words and punctuation, preserving multiword phrases."""
        cleaned = self._STOP_WORDS.sub(" ", query_text)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if cleaned else query_text

    def _detect_phrases(self, query_text: str) -> list[str]:
        """Detect quoted or common multiword phrases in the query."""
        phrases = []
        # Quoted phrases
        for m in re.finditer(r'"([^"]+)"', query_text):
            phrases.append(m.group(1).lower())
        # Common compound terms
        compounds = [
            "sick days", "sick leave", "vacation policy", "probation period",
            "onboarding", "resignation", "termination", "benefits",
            "handbook", "contract", "invoice", "submission",
        ]
        for c in compounds:
            if c in query_text.lower():
                phrases.append(c)
        return phrases

    def _compute_rerank_score(self, candidate: dict, phrases: list[str], query_text: str) -> float:
        """Deterministic reranking: phrase overlap + rare-term overlap + penalties."""
        text_lower = candidate["text"].lower()
        source_lower = candidate["source_id"].lower()

        # Phrase overlap (strong signal)
        phrase_hits = sum(1 for p in phrases if p in text_lower or p in source_lower)
        phrase_score = phrase_hits * 2.0

        # Rare-term overlap (terms not in question_terms)
        query_words = set(query_text.lower().split())
        rare_words = query_words - set(self._QUESTION_TERMS.findall(query_text.lower()))
        text_words = set(text_lower.split())
        rare_overlap = len(rare_words & text_words)
        rare_score = rare_overlap * 0.5

        # Source/document metadata match
        source_match = 1.0 if any(p in source_lower for p in phrases) else 0.0

        # BM25 base score (less negative = better)
        bm25_score = -candidate.get("rank", 0) / 10.0

        return bm25_score + phrase_score + rare_score + source_match

    def _query(self, query_text: str, top_k: int = 3) -> list[dict]:
        import sqlite3
        cleaned = self._normalize_query(query_text)
        phrases = self._detect_phrases(query_text)

        # Preserve phrases as quoted terms in FTS query
        fts_terms = cleaned.split()
        fts_parts = []
        for term in fts_terms:
            # Check if this term is part of a detected phrase
            in_phrase = any(term in p.split() for p in phrases)
            if in_phrase:
                fts_parts.append(f'"{term}"')
            else:
                fts_parts.append(term)
        fts_query = " OR ".join(fts_parts)

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT source_id, location, text, bm25(documents_fts) AS rank
               FROM documents_fts
               WHERE documents_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, top_k * 2),  # fetch extra for reranking
        ).fetchall()
        conn.close()

        candidates = [dict(r) for r in rows]

        # Rerank using deterministic scoring
        for c in candidates:
            c["rerank_score"] = self._compute_rerank_score(c, phrases, query_text)

        candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
        return candidates[:top_k]

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        query = context.request.text

        if not self._db_exists():
            evidence = {
                "source_id": "demo-policy.txt",
                "location": "demo",
                "text": f"Evidence selected for query: {query}",
                "retrieval_score": 0.84,
            }
            return ModuleResult(self.name, "success", evidence, 0.84,
                                metadata={"retrieval_status": "fallback_no_db", "evidence_sufficient": True})

        try:
            candidates = self._query(query, top_k=3)
        except Exception:
            candidates = []

        # Diagnostic metadata
        cleaned = self._normalize_query(query)
        fts_query = " OR ".join(cleaned.split())
        phrases = self._detect_phrases(query)

        diagnostics = {
            "raw_query": query,
            "normalized_query": cleaned,
            "fts_query": fts_query,
            "phrases_detected": phrases,
            "top_k_candidates": [
                {"source_id": c["source_id"], "bm25_rank": round(c["rank"], 2), "rerank_score": round(c["rerank_score"], 2), "text_excerpt": c["text"][:80]}
                for c in candidates
            ],
        }

        if not candidates:
            evidence = {
                "source_id": "demo-policy.txt",
                "location": "demo",
                "text": f"Evidence selected for query: {query}",
                "retrieval_score": 0.50,
            }
            diagnostics["retrieval_status"] = "no_match"
            diagnostics["evidence_sufficient"] = False
            diagnostics["retrieval_warnings"] = ["No FTS5 match found"]
            return ModuleResult(self.name, "success", evidence, 0.50, metadata=diagnostics)

        top = candidates[0]
        evidence = {
            "source_id": top["source_id"],
            "location": top["location"],
            "text": top["text"],
            "retrieval_score": 0.84,
        }

        diagnostics["selected_source_id"] = top["source_id"]
        diagnostics["retrieval_status"] = "success"
        diagnostics["evidence_sufficient"] = True
        diagnostics["retrieval_warnings"] = []

        return ModuleResult(self.name, "success", evidence, 0.84, metadata=diagnostics)


class SmallModel(BaseModule):
    name = "small_model"

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path or os.environ.get("CPU_INFERENCE_MODEL_PATH")
        self._llm = None

    def _load_model(self):
        if self._llm is not None:
            return
        if not self._model_path or not Path(self._model_path).exists():
            return
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self._model_path,
                n_ctx=512,
                n_threads=8,
                verbose=False,
            )
        except Exception:
            self._llm = None

    def _get_rss(self):
        """Get RSS bytes. Returns (current, peak, method)."""
        try:
            from scripts.process_rss import get_process_rss_bytes
            return get_process_rss_bytes()
        except ImportError:
            try:
                import sys as _sys
                _repo = Path(__file__).resolve().parent.parent.parent.parent
                _scripts = _repo / "scripts"
                if str(_scripts) not in _sys.path:
                    _sys.path.insert(0, str(_scripts))
                from process_rss import get_process_rss_bytes
                return get_process_rss_bytes()
            except Exception:
                return None, None, "rss_import_failed"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        # Collect RSS before model work
        rss_before, _, rss_method = self._get_rss()

        self._load_model()
        model_loaded = self._llm is not None
        load_time_ms = None  # Load time measured on first call only

        if not model_loaded:
            # Fallback: original demo behavior
            if context.analysis and context.analysis.task_type == "retrieval_qa":
                evidence = inputs.get("evidence", {})
                answer = f"Based on {evidence.get('source_id', 'the supplied evidence')}: {evidence.get('text', '')}"
            else:
                answer = f"Demo response for: {context.request.text}"
            rss_after, _, _ = self._get_rss()
            return ModuleResult(self.name, "success", answer, 0.5,
                                metadata={
                                    "model_metrics": {
                                        "model_name": Path(self._model_path).stem if self._model_path else None,
                                        "model_path_basename": Path(self._model_path).name if self._model_path else None,
                                        "model_loaded": False,
                                        "model_load_time_ms": None,
                                        "fallback_used": True,
                                        "fallback_reason": "no_model_configured" if not self._model_path else "model_load_failed",
                                        "input_tokens": None,
                                        "evidence_tokens": None,
                                        "output_tokens": None,
                                        "prompt_processing_time_ms": None,
                                        "generation_time_ms": None,
                                        "total_model_time_ms": None,
                                        "time_to_first_token_ms": None,
                                        "stop_reason": "fallback",
                                        "prompt_tokens_per_second": None,
                                        "generation_tokens_per_second": None,
                                        "process_rss_before_bytes": rss_before,
                                        "process_rss_after_bytes": rss_after,
                                        "process_rss_peak_bytes": rss_after,
                                        "rss_measurement_method": rss_method,
                                        "metrics_available": False,
                                        "metrics_unavailable_reason": "model not loaded",
                                    }
                                })

        try:
            user_text = inputs.get("prompt", context.request.text)

            # For retrieval routes, include evidence context in messages
            is_retrieval = (
                context.analysis
                and context.analysis.task_type == "retrieval_qa"
            )
            evidence = inputs.get("evidence", {}) if is_retrieval else {}
            source_id = evidence.get("source_id", "the supplied evidence")
            evidence_text = evidence.get("text", "")
            evidence_tokens = len(evidence_text) // 4 if evidence_text else 0

            if is_retrieval and evidence_text:
                messages = [
                    {"role": "system", "content": (
                        f"Answer the following question using ONLY the provided evidence. "
                        f"Include the source name '{source_id}' in your response."
                    )},
                    {"role": "user", "content": (
                        f"Evidence: {evidence_text}\n\nQuestion: {user_text}"
                    )},
                ]
            else:
                messages = [
                    {"role": "user", "content": user_text},
                ]

            total_start = time.perf_counter()
            result = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.0,
            )
            total_ms = (time.perf_counter() - total_start) * 1000

            text = result["choices"][0]["message"]["content"].strip()
            stop_reason = result["choices"][0].get("finish_reason", "unknown")
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Normalize stop reason
            if stop_reason not in ("stop", "length", "eos"):
                if "stop" in str(stop_reason).lower():
                    stop_reason = "stop"
                elif "length" in str(stop_reason).lower():
                    stop_reason = "length"
                else:
                    stop_reason = str(stop_reason)

            if not text:
                text = f"Demo response for: {context.request.text}"

            # For retrieval routes, ensure source_id is present in output
            if is_retrieval and source_id not in text:
                text = f"Based on {source_id}: {text}"

            # Collect RSS after
            rss_after, rss_peak, _ = self._get_rss()

            # Derive tokens/second
            prompt_tps = input_tokens / (total_ms / 1000) if total_ms > 0 and input_tokens > 0 else None
            gen_tps = output_tokens / (total_ms / 1000) if total_ms > 0 and output_tokens > 0 else None

            return ModuleResult(self.name, "success", text, 0.7,
                                metadata={
                                    "model_metrics": {
                                        "model_name": Path(self._model_path).stem if self._model_path else None,
                                        "model_path_basename": Path(self._model_path).name if self._model_path else None,
                                        "model_loaded": True,
                                        "model_load_time_ms": load_time_ms,
                                        "fallback_used": False,
                                        "fallback_reason": None,
                                        "input_tokens": input_tokens,
                                        "evidence_tokens": evidence_tokens,
                                        "output_tokens": output_tokens,
                                        "prompt_processing_time_ms": None,  # not available in llama-cpp-python 0.3.35
                                        "generation_time_ms": None,  # not available in llama-cpp-python 0.3.35
                                        "total_model_time_ms": round(total_ms, 1),
                                        "time_to_first_token_ms": None,  # no streaming/first-token measurement available
                                        "stop_reason": stop_reason,
                                        "prompt_tokens_per_second": round(prompt_tps, 2) if prompt_tps else None,
                                        "generation_tokens_per_second": round(gen_tps, 2) if gen_tps else None,
                                        "process_rss_before_bytes": rss_before,
                                        "process_rss_after_bytes": rss_after,
                                        "process_rss_peak_bytes": rss_peak,
                                        "rss_measurement_method": rss_method,
                                        "metrics_available": True,
                                        "metrics_unavailable_reason": None,
                                    }
                                })
        except Exception as exc:
            rss_after, _, _ = self._get_rss()
            return ModuleResult(
                self.name, "success",
                f"Demo response for: {context.request.text}",
                0.5, warnings=[f"LLM inference failed: {exc}"],
                metadata={
                    "model_metrics": {
                        "model_name": Path(self._model_path).stem if self._model_path else None,
                        "model_path_basename": Path(self._model_path).name if self._model_path else None,
                        "model_loaded": True,
                        "model_load_time_ms": load_time_ms,
                        "fallback_used": True,
                        "fallback_reason": "inference_error",
                        "input_tokens": None,
                        "evidence_tokens": None,
                        "output_tokens": None,
                        "prompt_processing_time_ms": None,
                        "generation_time_ms": None,
                        "total_model_time_ms": None,
                        "time_to_first_token_ms": None,
                        "stop_reason": "error",
                        "prompt_tokens_per_second": None,
                        "generation_tokens_per_second": None,
                        "process_rss_before_bytes": rss_before,
                        "process_rss_after_bytes": rss_after,
                        "process_rss_peak_bytes": rss_after,
                        "rss_measurement_method": rss_method,
                        "metrics_available": False,
                        "metrics_unavailable_reason": f"inference error: {exc}",
                    }
                },
            )


class InvoiceExtractor(BaseModule):
    name = "invoice_extractor"
    residency = Residency.WARM

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        text = context.request.text
        total_match = re.search(r"total\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
        tax_match = re.search(r"tax\s*[:$]?\s*(\d[\d,.]*\d|\d)", text, re.I)
        vendor_match = re.search(r"\bvendor\b\s*(?::|\s)\s*([^,\n]+?)\s*(?=,\s*(?:tax|total)\b|$)", text, re.I)
        output = {
            "vendor": vendor_match.group(1).strip() if vendor_match else None,
            "tax": float(tax_match.group(1).replace(",", "")) if tax_match else None,
            "total": float(total_match.group(1).replace(",", "")) if total_match else None,
        }
        missing = [key for key, value in output.items() if value is None]
        return ModuleResult(self.name, "success", output, 0.88 if not missing else 0.60,
                            [f"missing_{key}" for key in missing])


class ResponseRenderer(BaseModule):
    name = "response_renderer"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        if "calculation" in inputs:
            return ModuleResult(self.name, "success", inputs["calculation"]["formatted_result"])
        if "extraction" in inputs:
            return ModuleResult(self.name, "success", json.dumps(inputs["extraction"], sort_keys=True))
        return ModuleResult(self.name, "success", str(inputs.get("answer", "No answer produced.")))


class Verifier(BaseModule):
    name = "verifier"

    def run(self, context: ExecutionContext, inputs: Mapping[str, Any]) -> ModuleResult:
        if "extraction" in inputs:
            extraction = inputs["extraction"]
            if extraction.get("total") is None:
                return ModuleResult(self.name, "failed", warnings=["missing_total"], confidence=0.40)
        if "evidence" in inputs and inputs["evidence"].get("retrieval_score", 0) < 0.60:
            return ModuleResult(self.name, "failed", warnings=["weak_evidence"], confidence=0.50)
        return ModuleResult(self.name, "success", {"verified": True}, 0.98)


@dataclass
class Step:
    step_id: str
    module: str
    input_keys: tuple[str, ...] = ()
    output_key: Optional[str] = None
    condition: Optional[Callable[[ExecutionContext], bool]] = None


class ExecutionGraph:
    def __init__(self, steps: Iterable[Step], route_name: str):
        self.steps = list(steps)
        self.route_name = route_name

    def run(self, context: ExecutionContext, modules: Mapping[str, Module]) -> ExecutionResult:
        for step in self.steps:
            if step.condition and not step.condition(context):
                continue
            module = modules[step.module]
            inputs = {key: context.values[key] for key in step.input_keys if key in context.values}
            started = time.perf_counter()
            result = module.run(context, inputs)
            cpu_ms = (time.perf_counter() - started) * 1000
            if result.status != "success":
                context.traces.append(StepTrace(step.step_id, step.module, result.status, cpu_ms, "failed", result.warnings))
                return ExecutionResult(context.request.request_id, "needs_escalation", None,
                                       self.route_name, context.traces, True,
                                       ";".join(result.warnings) or f"step_failed:{step.step_id}")
            if step.output_key:
                context.values[step.output_key] = result.output
            context.traces.append(StepTrace(step.step_id, step.module, result.status, cpu_ms,
                                            _summarize(result.output), result.warnings,
                                            metadata=result.metadata))

        output = context.values.get("response", context.values.get("answer"))
        return ExecutionResult(context.request.request_id, "success", output,
                               self.route_name, context.traces)


def _summarize(value: Any) -> str:
    text = str(value)
    return text[:160] + "..." if len(text) > 160 else text


def normalize_key(request: Request) -> str:
    raw = json.dumps({"text": " ".join(request.text.lower().split()),
                      "attachments": request.attachments,
                      "permissions": request.permissions}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


class Runtime:
    def __init__(self):
        self.modules: Dict[str, Module] = {
            "request_analyzer": RequestAnalyzer(),
            "calculator": Calculator(),
            "document_retriever": DocumentRetriever(),
            "small_model": SmallModel(),
            "invoice_extractor": InvoiceExtractor(),
            "response_renderer": ResponseRenderer(),
            "verifier": Verifier(),
        }
        self.cache: dict[str, ExecutionResult] = {}

    def analyze(self, request: Request) -> Analysis:
        context = ExecutionContext(request)
        result = self.modules["request_analyzer"].run(context, {})
        assert isinstance(result.output, Analysis)
        return result.output

    def choose_graph(self, analysis: Analysis) -> ExecutionGraph:
        if analysis.recommended_route == "deterministic_calculation":
            return ExecutionGraph([
                Step("calculate", "calculator", output_key="calculation"),
                Step("render", "response_renderer", ("calculation",), "response"),
            ], "deterministic_calculation")
        if analysis.recommended_route == "invoice_extraction":
            return ExecutionGraph([
                Step("extract", "invoice_extractor", output_key="extraction"),
                Step("verify", "verifier", ("extraction",), "verification"),
                Step("render", "response_renderer", ("extraction",), "response"),
            ], "invoice_extraction")
        if analysis.recommended_route == "small_rag":
            return ExecutionGraph([
                Step("retrieve", "document_retriever", output_key="evidence"),
                Step("answer", "small_model", ("evidence",), "answer"),
                Step("verify", "verifier", ("evidence",), "verification"),
                Step("render", "response_renderer", ("answer",), "response"),
            ], "small_rag")
        return ExecutionGraph([
            Step("generate", "small_model", output_key="answer"),
            Step("render", "response_renderer", ("answer",), "response"),
        ], "small_direct")

    def execute(self, request: Request, use_cache: bool = True) -> ExecutionResult:
        key = normalize_key(request)
        if use_cache and key in self.cache:
            cached = self.cache[key]
            return ExecutionResult(request.request_id, cached.status, cached.output,
                                   "exact_cache", cached.traces)

        analysis = self.analyze(request)
        context = ExecutionContext(request, analysis)
        graph = self.choose_graph(analysis)
        result = graph.run(context, self.modules)
        if result.status == "success" and analysis.risk_level == "high":
            result.escalated = True
            result.escalation_reason = "high_risk_requires_policy_review"
        if result.status == "success":
            self.cache[key] = result
        return result


def trace_to_dict(result: ExecutionResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "status": result.status,
        "route": result.route,
        "output": result.output,
        "escalated": result.escalated,
        "escalation_reason": result.escalation_reason,
        "steps": [
            {
                "step_id": trace.step_id,
                "module": trace.module,
                "status": trace.status,
                "cpu_ms": round(trace.cpu_ms, 3),
                "output_summary": trace.output_summary,
                "warnings": trace.warnings,
                "metadata": trace.metadata,
            }
            for trace in result.traces
        ],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
