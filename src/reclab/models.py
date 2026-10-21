"""Train compact CPU rankers and serve a plain-array BPR artifact."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

from .data import history_map
from .rerank import rerank

REQUIRED_ARTIFACT_KEYS = {
    "schema_version", "model_version", "user_ids", "item_ids", "user_index",
    "item_index", "user_factors", "item_factors", "item_biases", "items",
    "seen_items", "popularity_scores", "long_tail_mask", "selected_lambda",
}


def fit_rankers(train: pd.DataFrame, config: dict) -> tuple[dict, dict]:
    """Train all baselines on the same positives and train-eligible catalog."""
    import cornac  # Training-only dependency; the serving process does not need it.

    positive = train.loc[train.rating >= config["positive_threshold"]].copy()
    users = np.sort(positive.user_id.unique()).astype(np.int64)
    items = np.sort(positive.item_id.unique()).astype(np.int64)
    user_index = {int(value): index for index, value in enumerate(users)}
    item_index = {int(value): index for index, value in enumerate(items)}
    rows = positive.user_id.map(user_index).to_numpy()
    cols = positive.item_id.map(item_index).to_numpy()
    binary = sparse.csr_matrix(
        (np.ones(len(positive), dtype=np.float32), (rows, cols)),
        shape=(len(users), len(items)),
    )
    popularity = np.asarray(binary.sum(axis=0)).ravel()
    overlap = (binary.T @ binary).toarray()
    denominator = popularity[:, None] + popularity[None, :] - overlap
    similarity = np.divide(
        overlap, denominator, out=np.zeros_like(overlap), where=denominator > 0,
    )
    np.fill_diagonal(similarity, 0.0)
    sar_scores = np.asarray(binary @ similarity, dtype=np.float32)
    data = cornac.data.Dataset.from_uir(
        ((str(int(row.user_id)), str(int(row.item_id)), 1.0)
         for row in positive.itertuples(index=False)),
        seed=config["seed"],
    )
    options = config["bpr"]
    model = cornac.models.BPR(
        k=options["factors"], max_iter=options["epochs"],
        learning_rate=options["learning_rate"], lambda_reg=options["lambda_reg"],
        use_bias=options["use_bias"], num_threads=1, seed=config["seed"],
        verbose=False,
    ).fit(data)
    # Cornac internally assigns IDs by encounter order; reorder explicitly.
    u_order = [data.uid_map[str(int(user))] for user in users]
    i_order = [data.iid_map[str(int(item))] for item in items]
    u_factors = np.asarray(model.u_factors[u_order], dtype=np.float32)
    i_factors = np.asarray(model.i_factors[i_order], dtype=np.float32)
    i_biases = np.asarray(model.i_biases[i_order], dtype=np.float32)
    bpr_scores = u_factors @ i_factors.T + i_biases
    head_order = np.lexsort((items, -popularity))
    tail = np.ones(len(items), dtype=bool)
    tail[head_order[:int(np.ceil(0.2 * len(items)))]] = False
    artifact = {
        "schema_version": 1, "user_ids": users, "item_ids": items,
        "user_index": user_index, "item_index": item_index,
        "user_factors": u_factors, "item_factors": i_factors,
        "item_biases": i_biases, "popularity_scores": popularity,
        "long_tail_mask": tail,
        "seen_items": {u: sorted(values) for u, values in history_map(train).items()},
        "training_positive_counts": positive.groupby("user_id").size().to_dict(),
        "cornac_version": cornac.__version__,
    }
    return artifact, {"popularity": popularity, "sar": sar_scores, "bpr": bpr_scores}


def validate_artifact(artifact: dict) -> dict:
    """Fail readiness on malformed shapes, non-finite parameters or bad IDs."""
    missing = REQUIRED_ARTIFACT_KEYS - artifact.keys()
    if missing:
        raise ValueError(f"Missing artifact keys: {sorted(missing)}")
    if artifact["schema_version"] != 1:
        raise ValueError("Unsupported artifact schema.")
    n_users, n_items = len(artifact["user_ids"]), len(artifact["item_ids"])
    uf, vf = artifact["user_factors"], artifact["item_factors"]
    if uf.ndim != 2 or vf.ndim != 2 or uf.shape != (n_users, vf.shape[1]):
        raise ValueError("Inconsistent factor dimensions.")
    if vf.shape[0] != n_items or len(artifact["items"]) != n_items:
        raise ValueError("Catalog and factors disagree.")
    for name in ("item_biases", "popularity_scores", "long_tail_mask"):
        if np.asarray(artifact[name]).shape != (n_items,):
            raise ValueError(f"Invalid {name} shape.")
    for name in ("user_factors", "item_factors", "item_biases", "popularity_scores"):
        if not np.isfinite(artifact[name]).all():
            raise ValueError(f"Non-finite {name}.")
    if len(set(artifact["item_ids"])) != n_items or len(set(artifact["user_ids"])) != n_users:
        raise ValueError("Duplicate model IDs.")
    for name in ("user", "item"):
        expected = {int(value): position for position, value in enumerate(artifact[f"{name}_ids"])}
        if artifact[f"{name}_index"] != expected:
            raise ValueError(f"Inconsistent {name} ID mapping.")
    if any(int(row["item_id"]) != int(item) for row, item in
           zip(artifact["items"], artifact["item_ids"], strict=True)):
        raise ValueError("Catalog metadata order differs from model item order.")
    if not 0 <= artifact["selected_lambda"] <= 1:
        raise ValueError("Invalid selected reranking weight.")
    return {"users": n_users, "items": n_items, "factors": uf.shape[1]}


def recommend(
    artifact: dict, user_id: int | None = None, k: int = 10,
    novelty_weight: float | None = None,
    preferred_genres: list[str] | None = None,
) -> list[dict]:
    """Return scored recommendations; scores are not probabilities or ratings."""
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 50:
        raise ValueError("k must be an integer in [1, 50].")
    weight = artifact["selected_lambda"] if novelty_weight is None else novelty_weight
    if not np.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("novelty_weight must be finite and in [0, 1].")
    user_position = artifact["user_index"].get(user_id)
    known = user_position is not None
    if known:
        scores = (
            artifact["user_factors"][user_position] @ artifact["item_factors"].T
            + artifact["item_biases"]
        ).astype(np.float64)
    else:
        scores = np.log1p(artifact["popularity_scores"].astype(np.float64))
        weight = 0.0  # A cold start has no personalized relevance model.
    for item in artifact["seen_items"].get(user_id, []):
        position = artifact["item_index"].get(item)
        if position is not None:
            scores[position] = -np.inf
    if preferred_genres:
        all_genres = {g for item in artifact["items"] for g in item["genres"]}
        if not set(preferred_genres).issubset(all_genres):
            raise ValueError("Unknown genre; use a genre present in the catalog.")
        mask = np.array([
            bool(set(preferred_genres).intersection(item["genres"]))
            for item in artifact["items"]
        ])
        scores[~mask] = -np.inf
    positions, mixed = rerank(
        scores, artifact["item_ids"], artifact["popularity_scores"], k, weight,
        max(k, artifact.get("config", {}).get("candidate_pool", 100)),
    )
    return [
        {
            "item_id": int(artifact["item_ids"][position]),
            "title": artifact["items"][position]["title"],
            "genres": artifact["items"][position]["genres"],
            "score": float(score), "base_score": float(scores[position]),
            "popularity": int(artifact["popularity_scores"][position]),
            "is_long_tail": bool(artifact["long_tail_mask"][position]),
            "reason": "personalized_bpr" if known else "cold_start_popularity",
        }
        for position, score in zip(positions, mixed, strict=True)
    ]
