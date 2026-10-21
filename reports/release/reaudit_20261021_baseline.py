"""Read-only independent P1 release audit; never invokes training or serving writes.

Uses raw input bytes and frozen arrays rather than the project's metric functions.
Only this audit's JSON is written. Run with the root .venv interpreter.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import joblib
import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT.parents[1]
DATA = WORK / "data/movielens"
UPSTREAM = WORK / "external/recommenders"
PIN = "aa8332189cd495be6ffaa7e1c8054f1c180b5ef3"
OUTPUT = ROOT / "reports/release/reaudit_20261021_baseline.json"
checks = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def command(args, cwd=ROOT):
    done = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return {"command": [str(x) for x in args], "exit_code": done.returncode,
            "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}


def check(name, passed, evidence):
    checks.append({"name": name, "passed": bool(passed), "evidence": evidence})
    print(f'{"PASS" if passed else "FAIL"}: {name}', flush=True)


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def environment(label, interpreter, lock):
    wanted = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        if "==" in line:
            key, value = line.strip().split("==", 1)
            wanted[norm(key)] = value
    observed = command([interpreter, "-m", "pip", "list", "--format=json"])
    actual = {norm(x["name"]): x["version"] for x in json.loads(observed["stdout"])}
    mismatches = {key: {"locked": value, "installed": actual.get(key)}
                  for key, value in wanted.items() if actual.get(key) != value}
    extras = {key: value for key, value in actual.items() if key not in wanted}
    # baseline freeze intentionally omits packaging tools; pip list includes them.
    dependency_check = command([interpreter, "-m", "pip", "check"])
    check(label + " dependency lock", not mismatches and dependency_check["exit_code"] == 0,
          {"lock_sha256": sha(lock), "locked_packages": len(wanted),
           "installed_packages": len(actual), "version_mismatches": mismatches,
           "extra_installed_packages": extras, "pip_check": dependency_check})


def notebook_text(cell):
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def notebook_metrics(nb):
    answer = {}
    for cell in nb["cells"]:
        for output in cell.get("outputs", []):
            data = output.get("data", {}).get("application/notebook_utils.json+json")
            if data:
                answer[data["name"]] = data["data"]
    return answer


def inspect_upstream():
    commit = command(["git", "rev-parse", "HEAD"], UPSTREAM)
    diff = command(["git", "diff", "--exit-code", PIN, "--", "recommenders", "examples"], UPSTREAM)
    check("Pinned upstream source checkout", commit["stdout"] == PIN and diff["exit_code"] == 0,
          {"commit": commit, "diff": diff, "license_sha256": sha(UPSTREAM / "LICENSE"),
           "copied_license_matches": sha(UPSTREAM / "LICENSE") == sha(ROOT / "baseline/UPSTREAM_LICENSE")})
    for model in ("sar", "bpr"):
        report = read(ROOT / f"reports/baseline/{model}_comparison.json")
        source = UPSTREAM / report["upstream_file"]
        original = read(source)
        executed = read(ROOT / f"reports/baseline/{model}_executed.ipynb")
        original_cells = [x for x in original["cells"] if x["cell_type"] == "code"]
        actual_cells = [x for x in executed["cells"] if x["cell_type"] == "code"]
        changes = []
        for index, (before, after) in enumerate(zip(original_cells, actual_cells[1:-1], strict=True)):
            expected = notebook_text(before).replace(
                "data = movielens.load_pandas_df(",
                f"data = movielens.load_pandas_df(\n    local_cache_path={str(DATA)!r},")
            if notebook_text(after) != expected:
                changes.append(index)
        errors = [x for cell in actual_cells for x in cell.get("outputs", []) if x.get("output_type") == "error"]
        expected_metrics, actual_metrics = notebook_metrics(original), notebook_metrics(executed)
        diffs = {name: actual_metrics[name] - expected_metrics[name]
                 for name in ("map", "ndcg", "precision", "recall")}
        details = read(ROOT / f"reports/baseline/{model}_run_details.json")
        check(model + " original notebook execution evidence", not changes and not errors
              and all(x.get("execution_count") is not None for x in actual_cells)
              and all(value == 0 for value in diffs.values())
              and sha(source) == report["upstream_notebook_sha256"]
              and all(actual_metrics[name] == details["metrics"][name] for name in diffs),
              {"source_sha256": sha(source), "executed_sha256": sha(ROOT / f"reports/baseline/{model}_executed.ipynb"),
               "original_code_cells": len(original_cells), "executed_code_cells": len(actual_cells),
               "execution_counts": [x.get("execution_count") for x in actual_cells],
               "unexpected_source_changes": changes, "error_count": len(errors),
               "source_saved_metrics": {key: expected_metrics[key] for key in diffs},
               "actual_output_metrics": {key: actual_metrics[key] for key in diffs}, "differences": diffs,
               "scope": "Re-read complete stored outputs and cell code; did not rerun notebooks or overwrite evidence."})


def inspect_bytes(summary):
    baseline_manifest = read(ROOT / "reports/baseline/data_manifest.json")
    data_audit = read(ROOT / "reports/experiment/data_audit.json")
    zips = [("ml-100k.zip", baseline_manifest["sha256"], {"ml-100k/" + key: (DATA / key, value)
             for key, value in baseline_manifest["extracted_file_sha256"].items()}),
            ("ml-1m.zip", "a6898adb50b9ca05aa231689da44c217cb524e7ebd39d264c56e2832f2c54e20",
             {"ml-1m/" + key: (DATA / "ml-1m" / key, value)
              for key, value in data_audit["source_hashes"].items()})]
    for filename, expected, children in zips:
        archive = DATA / filename
        actual = sha(archive)
        values = {}
        with zipfile.ZipFile(archive) as container:
            valid_zip = container.testzip() is None
            for member, (path, expected_child) in children.items():
                archive_hash = hashlib.sha256(container.read(member)).hexdigest()
                current_hash = sha(path)
                values[member] = {"sha256": current_hash, "archive_member_sha256": archive_hash,
                                  "matches_record_and_archive": current_hash == expected_child == archive_hash}
        check(filename + " immutable bytes", actual == expected and valid_zip
              and all(x["matches_record_and_archive"] for x in values.values()),
              {"sha256": actual, "bytes": archive.stat().st_size, "zip_crc_passed": valid_zip, "members": values})
    manifest = read(ROOT / "reports/release/local_model_snapshot.json")
    snapshots = []
    for item in manifest["files"]:
        current, saved = ROOT / item["source"], ROOT / item["snapshot"]
        snapshots.append({"source": item["source"], "snapshot": item["snapshot"],
                          "current_sha256": sha(current), "snapshot_sha256": sha(saved),
                          "bytes": current.stat().st_size,
                          "matches": sha(current) == sha(saved) == item["sha256"]
                          and current.stat().st_size == item["bytes"]})
    check("Current model/config/reports match version snapshot", all(x["matches"] for x in snapshots)
          and sha(ROOT / "artifacts/model.joblib") == summary["artifact"]["sha256"], snapshots)


def independent_metrics(summary):
    artifact = joblib.load(ROOT / "artifacts/model.joblib")
    ratings = pd.read_csv(DATA / "ml-1m/ratings.dat", sep="::", engine="python",
                          names=["user", "item", "rating", "time"])
    times = sorted(ratings.time)
    t1, t2 = times[int(len(times) * .7) - 1], times[int(len(times) * (.7 + .15)) - 1]
    train = ratings[ratings.time <= t1]
    validation = ratings[(ratings.time > t1) & (ratings.time <= t2)]
    test = ratings[ratings.time > t2]
    split_hashes = {}
    for name, frame in (("train", train), ("validation", validation), ("test", test)):
        raw = frame.sort_values(["time", "user", "item"])[["user", "item", "rating", "time"]].to_numpy(dtype="<i8")
        split_hashes[name] = hashlib.sha256(raw.tobytes()).hexdigest()
    check("Independent temporal split from raw ratings", split_hashes == summary["split"]["row_hashes"]
          and t1 == summary["split"]["train_cutoff"] and t2 == summary["split"]["validation_cutoff"],
          {"rows": len(ratings), "cutoffs": [t1, t2], "partition_rows": [len(train), len(validation), len(test)],
           "partition_hashes": split_hashes, "strict_order": bool(train.time.max() < validation.time.min() < test.time.min())})
    positive = train[train.rating >= 4]
    user_ids, item_ids = sorted(positive.user.unique()), sorted(positive.item.unique())
    user_index = {int(x): i for i, x in enumerate(user_ids)}
    item_index = {int(x): i for i, x in enumerate(item_ids)}
    counts = positive.groupby("item").size().reindex(item_ids).to_numpy()
    training_history = {int(u): set(map(int, g.item)) for u, g in train.groupby("user")}
    activity = positive.groupby("user").size().to_dict()
    head = set(sorted(range(len(item_ids)), key=lambda p: (-counts[p], item_ids[p]))[:math.ceil(.2 * len(item_ids))])
    tail = np.array([p not in head for p in range(len(item_ids))])
    check("Model catalog/popularity/history derive only from training", user_index == artifact["user_index"]
          and item_index == artifact["item_index"] and np.array_equal(counts, artifact["popularity_scores"])
          and np.array_equal(tail, artifact["long_tail_mask"])
          and training_history == {u: set(v) for u, v in artifact["seen_items"].items()}
          and activity == artifact["training_positive_counts"],
          {"users": len(user_ids), "catalog": len(item_ids), "head_items": len(head),
           "tail_items": int(tail.sum()), "selected_lambda": artifact["selected_lambda"], "protocol": artifact["protocol"]})
    matrix = sparse.csr_matrix((np.ones(len(positive), dtype=np.float32),
                (positive.user.map(user_index), positive.item.map(item_index))),
                shape=(len(user_ids), len(item_ids)))
    intersections = (matrix.T @ matrix).toarray()
    unions = counts[:, None] + counts[None, :] - intersections
    jaccard = np.divide(intersections, unions, out=np.zeros_like(intersections), where=unions != 0)
    np.fill_diagonal(jaccard, 0)
    scores = {
        "sar": np.asarray(matrix @ jaccard, dtype=np.float32),
        "bpr": artifact["user_factors"] @ artifact["item_factors"].T + artifact["item_biases"],
    }
    novelty = 1 - np.log1p(counts) / np.log1p(counts).max()
    result = {}
    per_users = {}

    def evaluate_future(future, observed, methods):
        history = {int(u): set(map(int, g.item)) for u, g in observed.groupby("user")}
        truth = collections.defaultdict(set)
        outside = seen = 0
        future_positive = future[future.rating >= 4]
        for row in future_positive.itertuples(index=False):
            if row.item not in item_index:
                outside += 1
            elif row.item in history.get(row.user, set()):
                seen += 1
            else:
                truth[int(row.user)].add(int(row.item))
        denominators = {"future_rows": len(future), "future_users": int(future.user.nunique()),
                        "positive_rows": len(future_positive), "positive_users": int(future_positive.user.nunique()),
                        "out_of_training_catalog_positive_rows": outside, "already_seen_positive_rows": seen,
                        "eligible_positive_rows": sum(map(len, truth.values())), "eligible_positive_users": len(truth),
                        "positive_users_without_eligible_target": int(future_positive.user.nunique()) - len(truth)}
        aggregates = {}
        details = {}
        for label, model, weight in methods:
            detail = {"warm": [], "cold": []}
            coverage = {"warm": set(), "cold": set()}
            for user, relevant in sorted(truth.items()):
                is_warm = user in user_index
                cohort = "warm" if is_warm else "cold"
                raw = counts if model == "popularity" or not is_warm else scores[model][user_index[user]]
                available = [p for p, item in enumerate(item_ids) if item not in history.get(user, set())]
                pool = sorted(available, key=lambda p: (-float(raw[p]), item_ids[p]))[:100]
                if weight and is_warm and model != "popularity":
                    lo, hi = float(min(raw[pool])), float(max(raw[pool]))
                    mixed = {p: (1-weight) * ((float(raw[p])-lo)/(hi-lo) if hi>lo else 0)
                              + weight*float(novelty[p]) for p in pool}
                    pool = sorted(pool, key=lambda p: (-mixed[p], item_ids[p]))
                chosen = pool[:10]
                ids = [int(item_ids[p]) for p in chosen]
                assert not (set(ids) & history.get(user, set()))
                hits = [int(item in relevant) for item in ids]
                ideal = sum(1/math.log2(r+2) for r in range(min(10, len(relevant))))
                ndcg = sum(hit/math.log2(r+2) for r, hit in enumerate(hits))/ideal
                recall = sum(hits)/len(relevant)
                long_tail = sum(p not in head for p in chosen)/len(chosen)
                coverage[cohort].update(ids)
                detail[cohort].append((user, ndcg, recall, long_tail))
            metrics = {"denominators": denominators}
            for cohort in ("warm", "cold"):
                users = detail[cohort]
                metrics[cohort] = {"users": len(users),
                    "ndcg_at_10": sum(x[1] for x in users)/len(users),
                    "recall_at_10": sum(x[2] for x in users)/len(users),
                    "long_tail_exposure": sum(x[3] for x in users)/len(users),
                    "catalog_coverage": len(coverage[cohort])/len(item_ids),
                    "unique_recommended_items": len(coverage[cohort])}
            aggregates[label], details[label] = metrics, detail
        return aggregates, details

    test_methods = [(x, x, 0) for x in ("popularity", "sar", "bpr")] + [("bpr_reranked", "bpr", .2)]
    result, per_users = evaluate_future(test, pd.concat([train, validation]), test_methods)
    errors = []
    for name, measured in result.items():
        if measured["denominators"] != summary["test"][name]["denominators"]:
            errors.append(name + ":denominators")
        for cohort in ("warm", "cold"):
            for metric, value in measured[cohort].items():
                if abs(value - summary["test"][name][cohort][metric]) > 1e-12:
                    errors.append(name + ":" + cohort + ":" + metric)
    check("Independent four-model test metrics and target denominators", not errors,
          {"method": "Separate Python sorting, scalar math.log2 metrics and raw-data cohort construction; no project metric or ranker function imported.",
           "mismatch_fields": errors, "absolute_tolerance": 1e-12, "observed": result})
    valmethods = [(str(w), "bpr", w) for w in summary["config"]["reranking"]["weights"]]
    val, _ = evaluate_future(validation, train, valmethods)
    minimum = val["0"]["warm"]["ndcg_at_10"] * .98
    feasible = [w for w in summary["config"]["reranking"]["weights"] if val[str(w)]["warm"]["ndcg_at_10"] >= minimum]
    selected = max(feasible, key=lambda w: (val[str(w)]["warm"]["long_tail_exposure"], val[str(w)]["warm"]["ndcg_at_10"], -w))
    check("Independent validation-only weight selection", selected == summary["selection"]["selected_weight"]
          and selected == artifact["selected_lambda"],
          {"selected_weight": selected, "minimum_validation_ndcg": minimum, "feasible_weights": feasible,
           "observed_sweep": {w: m["warm"] for w, m in val.items()}})
    base = np.array(per_users["bpr"]["warm"], dtype=float)
    changed = np.array(per_users["bpr_reranked"]["warm"], dtype=float)
    assert np.array_equal(base[:, 0], changed[:, 0])
    paired = {}
    for col, name in enumerate(("ndcg", "recall", "tail_exposure"), 1):
        difference = changed[:, col] - base[:, col]
        rng = np.random.default_rng(42)
        draws = np.mean(difference[rng.integers(0, len(difference), (1000, len(difference)))], axis=1)
        paired[name] = {"mean_difference": float(difference.mean()),
                        "paired_95_percent_interval": list(map(float, np.quantile(draws, [.025, .975])))}
    good = all(abs(paired[x]["mean_difference"] - summary["paired_bootstrap_reranked_minus_bpr"][x]["mean_difference"]) < 1e-12
               and np.allclose(paired[x]["paired_95_percent_interval"], summary["paired_bootstrap_reranked_minus_bpr"][x]["paired_95_percent_interval"], atol=1e-12, rtol=0)
               for x in paired)
    check("Independent paired bootstrap from freshly recomputed per-user results", good,
          {"draws": 1000, "seed": 42, "users": len(base), "observed": paired})


def main():
    summary = read(ROOT / "reports/experiment/summary.json")
    before = {str(path.relative_to(ROOT)): sha(path) for path in
              [ROOT / "artifacts/model.joblib", *list((ROOT / "reports/experiment").glob("*.json"))]}
    inspect_upstream()
    inspect_bytes(summary)
    environment("Main environment", ROOT / ".venv/Scripts/python.exe", ROOT / "requirements-lock.txt")
    environment("Baseline environment", ROOT / "baseline/.venv/Scripts/python.exe", ROOT / "baseline/requirements-lock.txt")
    first = read(ROOT / "reports/experiment/first_run_summary.json")
    compared = ["test", "selection_sha256_before_test", "paired_bootstrap_reranked_minus_bpr", "config", "split"]
    equal = {key: first[key] == summary[key] for key in compared}
    check("Two stored full experiment runs agree", all(equal.values()),
          {"field_equality": equal, "first_summary_sha256": sha(ROOT / "reports/experiment/first_run_summary.json"),
           "current_summary_sha256": sha(ROOT / "reports/experiment/summary.json"),
           "training_seconds": [first["training_seconds"], summary["training_seconds"]]})
    independent_metrics(summary)
    after = {path: sha(ROOT / path) for path in before}
    check("Frozen experiment and current model unchanged by audit", before == after, before)
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in
                     [*sorted((ROOT / "src/reclab").glob("*.py")), ROOT / "baseline/run_upstream.py",
                      ROOT / "baseline/check_bpr_math.py", ROOT / "baseline/setup.ps1"]}
    git = {"head": command(["git", "rev-parse", "HEAD"]),
           "version": command(["git", "rev-parse", "v0.1.0^{commit}"]),
           "status": command(["git", "status", "--short"]),
           "remote": command(["git", "ls-remote", "origin", "refs/heads/main", "refs/tags/v0.1.0", "refs/tags/v0.1.0^{}", "refs/tags/baseline-v1"])}
    findings = [{"severity": "review_required", "check": x["name"], "evidence": x["evidence"]}
                for x in checks if not x["passed"]]
    result = {"audit_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope": "P1 code, upstream evidence, raw data, experiment mathematics, frozen artifact, environment and version; teaching/UI and full 40-item signoff delegated to root.",
              "status": "PASS_SCOPED" if not findings else "FINDINGS_REQUIRE_REVIEW",
              "audit_script_sha256": sha(__file__), "checks": checks, "findings": findings,
              "current_source_sha256": source_hashes, "git": git,
              "limitations": ["Stored upstream notebooks were inspected cell by cell; they were not retrained for this audit.",
                              "Frozen model metrics were independently recomputed; model fitting was not repeated.",
                              "Current pytest/HTTP reruns are performed and recorded separately by root.",
                              "No claim of production capacity, online causal uplift, multi-seed robustness, activated cloud CI or learner mastery."]}
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks": len(checks), "findings": len(findings), "report": str(OUTPUT)}), flush=True)


if __name__ == "__main__":
    main()
