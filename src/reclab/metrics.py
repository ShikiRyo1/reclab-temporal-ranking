"""Full-catalog ranking metrics with explicit cohorts and paired uncertainty."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import eligible_targets
from .rerank import rank_topk, rerank


def ranking_metrics(recommended: list[int], relevant: set[int], k: int = 10) -> dict:
    """Binary NDCG uses min(k, eligible positives) as the ideal denominator."""
    if not relevant:
        raise ValueError("Ranking metrics need at least one eligible positive.")
    if len(recommended) != len(set(recommended)):
        raise ValueError("Recommendations must not contain duplicates.")
    hits = np.array([item in relevant for item in recommended[:k]], dtype=float)
    discount = 1.0 / np.log2(np.arange(2, len(hits) + 2))
    ideal = np.sum(1.0 / np.log2(np.arange(2, min(k, len(relevant)) + 2)))
    return {"ndcg": float(np.sum(hits * discount) / ideal),
            "recall": float(hits.sum() / len(relevant))}


def evaluate(
    artifact: dict, scores: np.ndarray, future: pd.DataFrame,
    history: dict[int, set[int]], k: int = 10,
    weight: float = 0.0, pool_size: int = 100,
) -> tuple[dict, pd.DataFrame]:
    """Score warm and cold cohorts; unknown users use the same popularity fallback."""
    item_ids = artifact["item_ids"]
    targets, counts = eligible_targets(future, item_ids, history)
    rows, recommended_items = [], {"warm": set(), "cold": set()}
    activity = np.array(list(artifact["training_positive_counts"].values()))
    activity_median = float(np.median(activity))
    for user, truth in sorted(targets.items()):
        position = artifact["user_index"].get(user)
        cohort = "warm" if position is not None else "cold"
        if scores.ndim == 1 or position is None:
            raw = artifact["popularity_scores"].astype(np.float64).copy()
            chosen_weight = 0.0
        else:
            raw = scores[position].astype(np.float64).copy()
            chosen_weight = weight
        for item in history.get(user, set()):
            index = artifact["item_index"].get(item)
            if index is not None:
                raw[index] = -np.inf
        chosen, _ = rerank(raw, item_ids, artifact["popularity_scores"],
                           k, chosen_weight, pool_size)
        ids = list(map(int, item_ids[chosen]))
        measured = ranking_metrics(ids, truth, k)
        recommended_items[cohort].update(ids)
        rows.append({
            "user_id": user, "cohort": cohort,
            "activity_slice": (
                "high_activity" if artifact["training_positive_counts"].get(user, 0)
                > activity_median else "low_activity"
            ),
            "eligible_positives": len(truth), "recommended_count": len(ids),
            "tail_exposure": float(artifact["long_tail_mask"][chosen].mean())
            if len(chosen) else 0.0,
            "mean_log_novelty": float(np.log2(
                (artifact["popularity_scores"].sum() + len(item_ids))
                / (artifact["popularity_scores"][chosen] + 1)
            ).mean()) if len(chosen) else 0.0,
            **measured,
        })
    frame = pd.DataFrame(rows)
    summary = {"denominators": counts, "catalog_size": len(item_ids),
               "training_user_activity_median": activity_median}
    for cohort in ("warm", "cold"):
        part = frame.loc[frame.cohort == cohort] if len(frame) else frame
        summary[cohort] = {
            "users": len(part),
            "ndcg_at_10": float(part.ndcg.mean()) if len(part) else None,
            "recall_at_10": float(part.recall.mean()) if len(part) else None,
            "long_tail_exposure": float(part.tail_exposure.mean()) if len(part) else None,
            "catalog_coverage": len(recommended_items[cohort]) / len(item_ids),
            "unique_recommended_items": len(recommended_items[cohort]),
            "mean_log_novelty": float(part.mean_log_novelty.mean()) if len(part) else None,
        }
    summary["warm_activity_slices"] = {
        label: {"users": len(group), "ndcg_at_10": float(group.ndcg.mean()),
                "recall_at_10": float(group.recall.mean())}
        for label, group in frame.loc[frame.cohort == "warm"].groupby("activity_slice")
    } if len(frame) else {}
    return summary, frame


def bootstrap_interval(values: np.ndarray, draws: int = 1000, seed: int = 42) -> list:
    """Resample users, not ratings, because each user contributes one metric."""
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return [None, None]
    rng = np.random.default_rng(seed)
    means = np.array([
        values[rng.integers(0, len(values), len(values))].mean()
        for _ in range(draws)
    ])
    return [float(value) for value in np.quantile(means, [0.025, 0.975])]


def paired_comparison(base: pd.DataFrame, changed: pd.DataFrame,
                      draws: int = 1000, seed: int = 42) -> dict:
    """Align the same warm users before forming paired bootstrap differences."""
    columns = ["user_id", "ndcg", "recall", "tail_exposure"]
    left = base.loc[base.cohort == "warm", columns]
    right = changed.loc[changed.cohort == "warm", columns]
    joined = left.merge(right, on="user_id", suffixes=("_base", "_changed"),
                        validate="one_to_one")
    if len(joined) != len(left) or len(left) != len(right):
        raise ValueError("Paired comparison requires identical user cohorts.")
    return {
        metric: {
            "mean_difference": float((joined[f"{metric}_changed"] -
                                      joined[f"{metric}_base"]).mean()),
            "paired_95_percent_interval": bootstrap_interval(
                (joined[f"{metric}_changed"] - joined[f"{metric}_base"]).to_numpy(),
                draws, seed,
            ),
        }
        for metric in ("ndcg", "recall", "tail_exposure")
    }
