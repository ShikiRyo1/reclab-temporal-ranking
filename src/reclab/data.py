"""Immutable MovieLens loading and leakage-aware global temporal partitions."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def sha256_file(path: str | Path) -> str:
    """Hash bytes, rather than filenames, to identify the exact source."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_movielens(directory: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load ML-1M without demographics; IDs remain original integer IDs."""
    directory = Path(directory)
    ratings = pd.read_csv(
        directory / "ratings.dat", sep="::", engine="python",
        names=["user_id", "item_id", "rating", "timestamp"],
        dtype={"user_id": "int32", "item_id": "int32", "rating": "int8",
               "timestamp": "int64"},
    )
    items = pd.read_csv(
        directory / "movies.dat", sep="::", engine="python", encoding="latin-1",
        names=["item_id", "title", "genres"],
    )
    if ratings.isna().any().any() or ratings.duplicated(["user_id", "item_id"]).any():
        raise ValueError("Ratings must be complete and unique by user/item.")
    if not ratings["rating"].between(1, 5).all():
        raise ValueError("MovieLens ratings must be in [1, 5].")
    if items["item_id"].duplicated().any():
        raise ValueError("Duplicate catalog item IDs.")
    if not set(ratings.item_id).issubset(set(items.item_id)):
        raise ValueError("A rated item is absent from item metadata.")
    return ratings, items


def temporal_split(
    ratings: pd.DataFrame, train_fraction: float = 0.7,
    validation_fraction: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Keep identical timestamps together; no time boundary crosses a split."""
    if not 0 < train_fraction < train_fraction + validation_fraction < 1:
        raise ValueError("Fractions must leave nonempty train/validation/test.")
    times = np.sort(ratings.timestamp.to_numpy())
    if len(times) < 3:
        raise ValueError("At least three interactions are required.")
    train_cutoff = int(times[int(len(times) * train_fraction) - 1])
    validation_cutoff = int(
        times[int(len(times) * (train_fraction + validation_fraction)) - 1]
    )
    train = ratings.loc[ratings.timestamp <= train_cutoff].copy()
    validation = ratings.loc[
        (ratings.timestamp > train_cutoff) & (ratings.timestamp <= validation_cutoff)
    ].copy()
    test = ratings.loc[ratings.timestamp > validation_cutoff].copy()
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Timestamp ties left an empty partition.")
    info = {
        "train_cutoff": train_cutoff, "validation_cutoff": validation_cutoff,
        "train_rows": len(train), "validation_rows": len(validation),
        "test_rows": len(test),
        "train_cutoff_utc": pd.to_datetime(train_cutoff, unit="s", utc=True).isoformat(),
        "validation_cutoff_utc": pd.to_datetime(
            validation_cutoff, unit="s", utc=True
        ).isoformat(),
    }
    return train, validation, test, info


def history_map(observed: pd.DataFrame) -> dict[int, set[int]]:
    """Every observed rating counts as seen, including ratings below four."""
    return {
        int(user): set(map(int, group.item_id))
        for user, group in observed.groupby("user_id", sort=True)
    }


def eligible_targets(
    future: pd.DataFrame, item_ids: np.ndarray, history: dict[int, set[int]],
    threshold: int = 4,
) -> tuple[dict[int, set[int]], dict]:
    """Remove unreachable targets while explicitly counting each exclusion."""
    positive = future.loc[future.rating >= threshold]
    catalog = set(map(int, item_ids))
    targets: dict[int, set[int]] = {}
    absent, already_seen = 0, 0
    for row in positive.itertuples(index=False):
        user, item = int(row.user_id), int(row.item_id)
        if item not in catalog:
            absent += 1
        elif item in history.get(user, set()):
            already_seen += 1
        else:
            targets.setdefault(user, set()).add(item)
    return targets, {
        "future_rows": len(future), "future_users": int(future.user_id.nunique()),
        "positive_rows": len(positive),
        "positive_users": int(positive.user_id.nunique()),
        "out_of_training_catalog_positive_rows": absent,
        "already_seen_positive_rows": already_seen,
        "eligible_positive_rows": sum(map(len, targets.values())),
        "eligible_positive_users": len(targets),
        "positive_users_without_eligible_target": int(positive.user_id.nunique()) - len(targets),
    }
