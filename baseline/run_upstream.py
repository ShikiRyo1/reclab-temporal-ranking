"""Execute the two pinned upstream notebooks; retain originals and explicit adaptations."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

COMMIT = "aa8332189cd495be6ffaa7e1c8054f1c180b5ef3"
ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
UPSTREAM = WORKSPACE / "external" / "recommenders"
DATA = WORKSPACE / "data" / "movielens"
REPORT = ROOT / "reports" / "baseline"
NOTEBOOKS = {
    "sar": "examples/00_quick_start/sar_movielens.ipynb",
    "bpr": "examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb",
}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def metadata(nb):
    found = {}
    for cell in nb.cells:
        for output in cell.get("outputs", []):
            value = output.get("data", {}).get("application/notebook_utils.json+json")
            if value:
                found[value["name"]] = value["data"]
    return found

def setup():
    import truststore
    truststore.inject_into_ssl()  # Use the Windows/OS certificate store, with verification enabled.
    import requests
    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    actual = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    if actual != COMMIT:
        raise RuntimeError(f"Upstream commit differs: {actual}")
    archive = DATA / "ml-100k.zip"
    url = "https://files.grouplens.org/datasets/movielens/ml-100k.zip"
    if not archive.exists():
        response = requests.get(url, timeout=(15, 120))
        response.raise_for_status()
        temporary = archive.with_suffix(".zip.part")
        temporary.write_bytes(response.content)
        temporary.replace(archive)
    import zipfile
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError("MovieLens ZIP integrity check failed")
        (REPORT / "MovieLens_100K_TERMS.txt").write_bytes(zipped.read("ml-100k/README"))
    write_json(REPORT / "data_manifest.json", {
        "source": url, "local_archive": str(archive), "bytes": archive.stat().st_size,
        "sha256": sha(archive), "dataset": "MovieLens 100K",
        "redistribution": "Do not publish raw data or sample records; see provider README.",
    })
    shutil.copyfile(UPSTREAM / "LICENSE", ROOT / "baseline" / "UPSTREAM_LICENSE")
    # Keep the kernel inside this project; no global kernel installation is needed.
    kernel_root = ROOT / "baseline" / ".jupyter"
    kernel = kernel_root / "kernels" / "p1-baseline"
    kernel.mkdir(parents=True, exist_ok=True)
    write_json(kernel / "kernel.json", {
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "P1 upstream baseline", "language": "python",
    })
    os.environ["JUPYTER_PATH"] = str(kernel_root)
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # Reduce unrelated BLAS scheduling variance, without changing Cornac parameters.
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"

def run(name: str):
    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter
    source = UPSTREAM / NOTEBOOKS[name]
    original = nbformat.read(source, as_version=4)
    nb = nbformat.read(source, as_version=4)
    preamble = nbformat.v4.new_code_cell(
        "import sys\n"
        f"sys.path.insert(0, {str(UPSTREAM)!r})\n"
        "print('Pinned source commit: " + COMMIT + "')\n"
    )
    preamble.metadata["local_adaptation"] = "Source path only; model and split parameters unchanged."
    nb.cells.insert(0, preamble)
    changes = []
    for cell in nb.cells[1:]:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
            if "data = movielens.load_pandas_df(" in cell.source:
                cell.source = cell.source.replace(
                    "data = movielens.load_pandas_df(",
                    f"data = movielens.load_pandas_df(\n    local_cache_path={str(DATA)!r},"
                )
                changes.append("Added only local_cache_path to load_pandas_df; dataset bytes unchanged.")
    summary_path = REPORT / f"{name}_run_details.json"
    # Add evidence capture after every original cell. Do not alter original model/evaluation logic.
    capture = (
        "import json, hashlib\n"
        "from pathlib import Path\n"
        "def frame_hash(frame):\n"
        "    return hashlib.sha256(frame.to_csv(index=False, lineterminator='\\n').encode()).hexdigest()\n"
        "details = {\n"
        " 'train_rows': len(train), 'test_rows': len(test),\n"
        " 'train_users': int(train.userID.nunique()), 'test_users': int(test.userID.nunique()),\n"
        " 'train_items': int(train.itemID.nunique()), 'test_items': int(test.itemID.nunique()),\n"
        " 'train_sha256': frame_hash(train), 'test_sha256': frame_hash(test),\n"
        " 'data_rows': len(data), 'seed': 42,\n"
        " 'metrics': {'map': float(eval_map), 'ndcg': float(eval_ndcg),\n"
        "             'precision': float(eval_precision), 'recall': float(eval_recall)}\n"
        "}\n"
    )
    if name == "sar":
        capture += (
            "details['rating_metrics'] = {key: float(value) for key,value in "
            "{'rmse':eval_rmse,'mae':eval_mae,'r2':eval_rsquared,'explained_variance':eval_exp_var,'logloss':eval_logloss}.items()}\n"
            "details['train_seconds'] = train_time.interval\n"
            "details['prediction_seconds'] = test_time.interval\n"
            "details['prediction_rows'] = len(top_k)\n"
        )
    else:
        capture += "details['prediction_rows'] = len(all_predictions)\n"
    capture += f"Path({str(summary_path)!r}).write_text(json.dumps(details, indent=2), encoding='utf-8')\nprint(details)\n"
    nb.cells.append(nbformat.v4.new_code_cell(capture))
    started = time.perf_counter()
    output = REPORT / f"{name}_executed.ipynb"
    client = NotebookClient(nb, timeout=1200, kernel_name="p1-baseline", resources={"metadata": {"path": str(REPORT)}})
    try:
        client.execute()
    finally:
        nbformat.write(nb, output)
    html, _ = HTMLExporter().from_notebook_node(nb)
    (REPORT / f"{name}_executed.html").write_text(html, encoding="utf-8")
    current = metadata(nb)
    saved = metadata(original)
    comparison = {
        "model": name, "status": "ALL_ORIGINAL_CELLS_EXECUTED",
        "upstream_commit": COMMIT, "upstream_file": NOTEBOOKS[name],
        "upstream_notebook_sha256": sha(source), "elapsed_seconds": time.perf_counter() - started,
        "original_code_cells": sum(c.cell_type == "code" for c in original.cells),
        "executed_code_cells": sum(c.cell_type == "code" and c.execution_count is not None for c in nb.cells),
        "adaptations": ["Prepended sys.path for pinned source checkout.", *changes,
                        "Appended evidence export cell; no model/split/evaluator changes."],
        "saved_upstream_metrics": saved, "observed_metrics": current,
        "metric_absolute_differences": {k: abs(current[k] - saved[k]) for k in ("map", "ndcg", "precision", "recall")},
        "exact_metric_tolerance": 1e-6,
        "numeric_match_at_tolerance": all(abs(current[k] - saved[k]) <= 1e-6 for k in ("map", "ndcg", "precision", "recall")),
        "notebook": str(output), "html": str(REPORT / f"{name}_executed.html"),
        "important": "Notebook/HTML contains source dataset sample records: keep local, do not publish.",
    }
    write_json(REPORT / f"{name}_comparison.json", comparison)
    print(json.dumps(comparison, indent=2), flush=True)
    return comparison

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["sar", "bpr", "all"], default="all")
    args = parser.parse_args()
    setup()
    versions = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (ROOT / "baseline" / "requirements-lock.txt").write_text(versions, encoding="utf-8")
    write_json(REPORT / "environment.json", {
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "numpy_constraint": "<2 required by upstream",
        "cornac_note": "2.3.0 uses numpy<2/scipy<=1.13.1; newer 2.3.5 requires numpy>2.",
        "requirements_lock": "baseline/requirements-lock.txt",
    })
    names = NOTEBOOKS if args.model == "all" else [args.model]
    results = [run(name) for name in names]
    write_json(REPORT / "baseline_execution_summary.json", results)

if __name__ == "__main__":
    main()

