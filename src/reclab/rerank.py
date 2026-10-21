"""Deterministic novelty reranking with an explicitly bounded candidate pool."""
from __future__ import annotations

import numpy as np


def rank_topk(scores: np.ndarray, item_ids: np.ndarray, k: int) -> np.ndarray:
    """Return array positions; break score ties by original item ID."""
    if k < 1 or len(scores) != len(item_ids):
        raise ValueError("k must be positive and score/item shapes must match.")
    valid = np.flatnonzero(np.isfinite(scores))
    order = np.lexsort((item_ids[valid], -scores[valid]))
    return valid[order[:k]]


def novelty_scores(popularity: np.ndarray) -> np.ndarray:
    """Training counts alone define novelty; a larger value means less popular."""
    values = np.log1p(np.asarray(popularity, dtype=np.float64))
    maximum = float(values.max(initial=0.0))
    return np.ones_like(values) if maximum == 0 else 1.0 - values / maximum


def rerank(
    scores: np.ndarray, item_ids: np.ndarray, popularity: np.ndarray,
    k: int = 10, weight: float = 0.0, pool_size: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    """Mix normalized relevance and novelty within base top-pool candidates."""
    if not 0 <= weight <= 1 or pool_size < k:
        raise ValueError("weight must be in [0, 1] and pool_size >= k.")
    pool = rank_topk(scores, item_ids, pool_size)
    if not len(pool):
        return pool, np.array([], dtype=float)
    raw = np.asarray(scores[pool], dtype=np.float64)
    span = float(raw.max() - raw.min())
    relevance = (raw - raw.min()) / span if span > 0 else np.zeros_like(raw)
    mixed = (1.0 - weight) * relevance + weight * novelty_scores(popularity)[pool]
    # At weight zero, preserve the full precision base order exactly.
    order = np.arange(len(pool)) if weight == 0 else np.lexsort((item_ids[pool], -mixed))
    chosen = order[:k]
    return pool[chosen], mixed[chosen]
