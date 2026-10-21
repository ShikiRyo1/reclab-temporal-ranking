"""Frozen validation selection and one locked temporal test evaluation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .data import history_map, load_movielens, sha256_file, temporal_split
from .metrics import bootstrap_interval, evaluate, paired_comparison
from .models import fit_rankers, recommend, validate_artifact

ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: dict | list) -> None:
    """Convert NumPy scalar metadata without losing the original numeric value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=lambda x: x.item()) + "\n",
        encoding="utf-8",
    )


def partition_hash(frame: pd.DataFrame) -> str:
    """Fingerprint the exact sorted interaction rows without redistributing them."""
    ordered = frame.sort_values(["timestamp", "user_id", "item_id"])
    array = ordered[["user_id", "item_id", "rating", "timestamp"]].to_numpy(dtype="<i8")
    return hashlib.sha256(array.tobytes()).hexdigest()


def make_plots(summary: dict, sweep: list, output: Path) -> None:
    """All chart coordinates are measured outputs; no anticipated gains appear."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ["popularity", "sar", "bpr", "bpr_reranked"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), constrained_layout=True)
    for axis, key, label in zip(
        axes, ["ndcg_at_10", "long_tail_exposure", "catalog_coverage"],
        ["NDCG@10", "Long-tail exposure", "Catalog coverage"], strict=True,
    ):
        values = [summary["test"][name]["warm"][key] for name in names]
        axis.bar(["Popular", "SAR-style", "BPR", "BPR+novelty"], values,
                 color=["#9AA5B1", "#7293CB", "#3B6DAA", "#2A9D8F"])
        axis.set_title(label)
        axis.tick_params(axis="x", labelrotation=20)
        axis.set_ylim(bottom=0)
    fig.suptitle("MovieLens 1M | global temporal holdout | warm users")
    fig.savefig(output / "test_metrics.png", dpi=180)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(6, 4), constrained_layout=True)
    axis.plot([r["warm"]["ndcg_at_10"] for r in sweep],
              [r["warm"]["long_tail_exposure"] for r in sweep], "o-")
    for row in sweep:
        if row["weight"] in (0, 0.1, 0.2, 0.35, 0.5):
            offset = (-45, -9) if row["weight"] == 0 else (5, 5)
            axis.annotate(f'w={row["weight"]:g}',
                          (row["warm"]["ndcg_at_10"], row["warm"]["long_tail_exposure"]),
                          xytext=offset, textcoords="offset points", fontsize=8)
    selected = summary["selection"]["validation_selected_metrics"]["warm"]
    axis.scatter(selected["ndcg_at_10"], selected["long_tail_exposure"],
                 s=100, facecolors="none", edgecolors="#2A9D8F", linewidths=2,
                 label="Selected on validation")
    xmin, xmax = axis.get_xlim()
    axis.set_xlim(xmin, xmax + 0.0006)
    axis.axvline(summary["selection"]["minimum_validation_ndcg"], color="#D66A42",
                 linestyle="--", label="98% relevance constraint")
    axis.set(xlabel="Validation NDCG@10", ylabel="Long-tail exposure",
             title="Validation trade-off curve")
    axis.legend()
    fig.savefig(output / "validation_tradeoff.png", dpi=180)
    plt.close(fig)


def run(data_dir: Path, config_path: Path, output: Path, artifact_path: Path) -> dict:
    """Freeze the weight selection on disk before evaluating the test window."""
    started = time.perf_counter()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("k") != 10 or config.get("positive_threshold") != 4:
        raise ValueError(
            "This protocol supports only k=10 and positive_threshold=4. "
            "Extend the metric implementation and protocol together before changing them."
        )
    output.mkdir(parents=True, exist_ok=True)
    private = output / "private"
    private.mkdir(exist_ok=True)
    ratings, movies = load_movielens(data_dir)
    train, validation, test, split = temporal_split(
        ratings, config["train_fraction"], config["validation_fraction"],
    )
    source_hashes = {name: sha256_file(data_dir / name)
                     for name in ("ratings.dat", "movies.dat", "README")}
    split["row_hashes"] = {name: partition_hash(frame) for name, frame in
                           (("train", train), ("validation", validation), ("test", test))}
    write_json(output / "data_audit.json", {
        "dataset": config["dataset"], "source_hashes": source_hashes,
        "ratings": len(ratings), "users": int(ratings.user_id.nunique()),
        "rated_items": int(ratings.item_id.nunique()), "split": split,
        "all_training_before_validation": bool(train.timestamp.max() < validation.timestamp.min()),
        "all_validation_before_test": bool(validation.timestamp.max() < test.timestamp.min()),
    })
    print(f"Loaded {len(ratings):,} ratings; train={len(train):,}, "
          f"validation={len(validation):,}, test={len(test):,}", flush=True)
    training_started = time.perf_counter()
    artifact, scores = fit_rankers(train, config)
    training_seconds = time.perf_counter() - training_started
    training_history = history_map(train)
    test_history = history_map(pd.concat([train, validation], ignore_index=True))
    catalog = movies.set_index("item_id").loc[artifact["item_ids"]]
    artifact["items"] = [
        {"item_id": int(item), "title": row.title, "genres": row.genres.split("|")}
        for item, row in catalog.iterrows()
    ]
    artifact.update({
        "config": config, "dataset": config["dataset"], "trained_through_utc": split["train_cutoff_utc"],
        "model_version": f'ml1m-bpr-{source_hashes["ratings.dat"][:8]}-seed{config["seed"]}',
        "selected_lambda": 0.0,
    })
    validation_results, sweep = {}, []
    for name in ("popularity", "sar", "bpr"):
        measured, _ = evaluate(artifact, scores[name], validation, training_history,
                              config["k"], pool_size=config["candidate_pool"])
        validation_results[name] = measured
    for weight in config["reranking"]["weights"]:
        measured, _ = evaluate(artifact, scores["bpr"], validation, training_history,
                              config["k"], weight, config["candidate_pool"])
        sweep.append({"weight": weight, **measured})
    threshold = validation_results["bpr"]["warm"]["ndcg_at_10"] * (
        1.0 - config["reranking"]["maximum_validation_ndcg_relative_loss"]
    )
    feasible = [row for row in sweep if row["warm"]["ndcg_at_10"] >= threshold]
    chosen = max(feasible, key=lambda row: (
        row["warm"]["long_tail_exposure"], row["warm"]["ndcg_at_10"], -row["weight"],
    ))
    selection = {
        "selected_weight": chosen["weight"], "minimum_validation_ndcg": threshold,
        "maximum_relative_ndcg_loss": config["reranking"]["maximum_validation_ndcg_relative_loss"],
        "selection_objective": config["reranking"]["selection_objective"],
        "source_config_sha256": sha256_file(config_path),
        "selected_before_test_evaluation": True,
        "validation_selected_metrics": chosen,
    }
    artifact["selected_lambda"] = chosen["weight"]
    artifact["model_version"] = (
        f'ml1m-bpr-{source_hashes["ratings.dat"][:8]}-'
        f'{selection["source_config_sha256"][:8]}-w{chosen["weight"]:g}'
    )
    artifact["protocol"] = {
        "name": "global-temporal-70-15-15-frozen-train-v1",
        "factors_cutoff_utc": split["train_cutoff_utc"],
        "serving_history_cutoff_utc": split["train_cutoff_utc"],
        "test_history_cutoff_utc": split["validation_cutoff_utc"],
        "serving_mode": "historical training snapshot; no online history updates",
    }
    write_json(output / "validation_sweep.json", sweep)
    write_json(output / "selected_config.json", selection)
    selection_hash = sha256_file(output / "selected_config.json")
    print(f"Training completed in {training_seconds:.2f}s; frozen weight="
          f'{chosen["weight"]}, selection_sha256={selection_hash}', flush=True)
    test_results, per_user = {}, {}
    for name in ("popularity", "sar", "bpr", "bpr_reranked"):
        score_name = "bpr" if name == "bpr_reranked" else name
        weight = chosen["weight"] if name == "bpr_reranked" else 0.0
        measured, frame = evaluate(artifact, scores[score_name], test, test_history,
                                  config["k"], weight, config["candidate_pool"])
        for metric, column in (("ndcg_at_10", "ndcg"), ("recall_at_10", "recall")):
            measured["warm"][f"{metric}_95_percent_interval"] = bootstrap_interval(
                frame.loc[frame.cohort == "warm", column].to_numpy(),
                config["bootstrap_samples"], config["seed"],
            )
        frame.to_csv(private / f"{name}_test_users.csv", index=False)
        test_results[name], per_user[name] = measured, frame
        print(f"{name}: warm NDCG={measured['warm']['ndcg_at_10']:.6f}, "
              f"tail exposure={measured['warm']['long_tail_exposure']:.6f}", flush=True)
    uncertainty = paired_comparison(
        per_user["bpr"], per_user["bpr_reranked"],
        config["bootstrap_samples"], config["seed"],
    )
    summary = {
        "protocol": "global-temporal-70-15-15-frozen-train-v1",
        "data": {"rows": len(ratings), "users": int(ratings.user_id.nunique()),
                 "train_catalog_items": len(artifact["item_ids"]),
                 "train_positive_users": len(artifact["user_ids"])},
        "split": split, "config": config, "selection": selection,
        "selection_sha256_before_test": selection_hash,
        "validation_baselines": validation_results, "test": test_results,
        "paired_bootstrap_reranked_minus_bpr": uncertainty,
        "training_seconds": training_seconds,
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: importlib.metadata.version(name)
                         for name in ("numpy", "pandas", "scipy", "cornac", "joblib")},
        },
        "limitations": [
            "Historical explicit ratings; absent ratings do not prove dislike.",
            "Warm primary metrics exclude unreachable targets; denominators/cold fallback reported.",
            "Frozen training at first cutoff; test history filter includes validation observations.",
            "One temporal split and one seed; bootstrap covers users, not training variation.",
            "Offline exposure/accuracy are not online satisfaction, revenue or causal uplift.",
            "Catalog metadata and model artifacts stay local under dataset restrictions.",
        ],
    }
    artifact["metrics_summary"] = {
        "test": test_results, "selected_weight": chosen["weight"], "protocol": summary["protocol"],
    }
    validate_artifact(artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path, compress=3)
    loaded = joblib.load(artifact_path)
    sample_user = int(artifact["user_ids"][0])
    expected = recommend(artifact, sample_user)
    observed = recommend(loaded, sample_user)
    if observed != expected:
        raise AssertionError("Saved/loaded serving predictions differ.")
    summary["artifact"] = {
        "sha256": sha256_file(artifact_path), "bytes": artifact_path.stat().st_size,
        "load_save_predictions_equal": True, "shape_validation": validate_artifact(loaded),
    }
    summary["elapsed_seconds"] = time.perf_counter() - started
    write_json(output / "summary.json", summary)
    make_plots(summary, sweep, output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/temporal_1m.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/experiment")
    parser.add_argument("--artifact", type=Path, default=ROOT / "artifacts/model.joblib")
    args = parser.parse_args()
    run(args.data_dir, args.config, args.output, args.artifact)


if __name__ == "__main__":
    main()
