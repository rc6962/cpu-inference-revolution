"""Model-tier registry for adaptive cascade serving.

Tiers:
  none   — deterministic/no-model path (calculations, cache hits)
  fast   — 1.5B Q4_K_M model
  strong — 3B Q4_K_M model
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class TierSpec:
    name: str
    model_path: str | None  # None for deterministic/no-model tier
    model_stem: str | None
    model_basename: str | None

    @property
    def is_model_backed(self) -> bool:
        return self.model_path is not None


# ── Canonical tier registry ──

TIER_NONE = TierSpec(
    name="none",
    model_path=None,
    model_stem=None,
    model_basename=None,
)

def _resolve_model_path(filename: str) -> str:
    """Resolve model path relative to repo root."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    if not (repo_root / "models").exists():
        cwd = Path.cwd()
        for p in [cwd, *cwd.parents]:
            if (p / "models").exists():
                repo_root = p
                break
    return str(repo_root / "models" / filename)

TIER_FAST = TierSpec(
    name="fast",
    model_path=_resolve_model_path("qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    model_stem="qwen2.5-1.5b-instruct-q4_k_m",
    model_basename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
)

TIER_STRONG = TierSpec(
    name="strong",
    model_path=_resolve_model_path("qwen2.5-3b-instruct-q4_k_m.gguf"),
    model_stem="qwen2.5-3b-instruct-q4_k_m",
    model_basename="qwen2.5-3b-instruct-q4_k_m.gguf",
)

TIERS: dict[str, TierSpec] = {
    "none": TIER_NONE,
    "fast": TIER_FAST,
    "strong": TIER_STRONG,
}


def get_tier(name: str) -> TierSpec:
    """Look up a tier by name. Raises KeyError if unknown."""
    if name not in TIERS:
        raise KeyError(f"Unknown tier: {name!r}. Valid: {list(TIERS)}")
    return TIERS[name]


def tier_for_model_path(model_path: str | None) -> TierSpec:
    """Return the tier that matches a given model path, or TIER_NONE."""
    if model_path is None:
        return TIER_NONE
    for tier in TIERS.values():
        if tier.model_path and Path(tier.model_path) == Path(model_path):
            return tier
    return TIER_NONE
