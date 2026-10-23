"""Recheck the 0.1.2 numeric contract over real HTTP without fitting a model."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys

import httpx
import reclab

ROOT = Path(__file__).resolve().parents[2]
def verify(output):
    result = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
    invalid = [
        {"k": True}, {"k": False}, {"k": "10"}, {"k": 10.0},
        {"user_id": True}, {"user_id": False}, {"user_id": "1161"}, {"user_id": 1161.0},
        {"novelty_weight": True}, {"novelty_weight": False}, {"novelty_weight": "0.2"},
    ]
    with httpx.Client(base_url="http://127.0.0.1:8011", timeout=30) as client:
        for payload in invalid:
            response = client.post("/recommendations", json=payload)
            field = next(iter(payload))
            detail = response.json().get("detail", [])
            passed = (response.status_code == 422 and detail[0]["loc"] == ["body", field])
            result["checks"].append({"payload": payload, "status": response.status_code,
                                     "expected": "422 for the named field", "passed": passed})
        for weight, expected in [(0, 0.0), (1, 1.0), (0.2, 0.2), (None, 0.2)]:
            payload = {"user_id": 1161, "k": 10, "novelty_weight": weight}
            response = client.post("/recommendations", json=payload)
            body = response.json()
            passed = (response.status_code == 200 and body["strategy"] == "personalized_bpr"
                      and body["novelty_weight"] == expected
                      and body["requested_novelty_weight"] == expected
                      and body["returned_k"] == 10)
            result["checks"].append({"payload": payload, "status": response.status_code,
                                     "expected_effective_weight": expected, "passed": passed})
        result["api_version"] = client.get("/openapi.json").json()["info"]["version"]
        result["ready"] = client.get("/ready").json()
    digest = hashlib.sha256((ROOT / "artifacts/model.joblib").read_bytes()).hexdigest()
    result["artifact_unchanged"] = (digest == result["ready"]["artifact_sha256"] ==
        "14874e07e00af8f4d9b4e94f51ebb0b368a6fdc5b98391697a4f6c846fb8b5ad")
    result["model_version_unchanged"] = (result["ready"]["model_version"] ==
                                         "ml1m-bpr-506d64ca-30794fbd-w0.2")
    version_code = ("import json,reclab,importlib.metadata as m;"
                    "print(json.dumps({'package':reclab.__version__,"
                    "'distribution':m.version('reclab-portfolio')}))")
    container = subprocess.run(["docker", "compose", "exec", "-T", "recommender", "python",
                                "-c", version_code], cwd=ROOT, text=True, capture_output=True,
                               check=True)
    result["container_versions"] = json.loads(container.stdout)
    result["local_versions"] = {"package": reclab.__version__,
                                "distribution": metadata.version("reclab-portfolio")}
    result["version_consistency"] = all(v == "0.1.2" for v in [result["api_version"],
        *result["container_versions"].values(), *result["local_versions"].values()])
    lock_mismatches = []
    pinned_count = 0
    for line in (ROOT / "requirements-lock.txt").read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            name, expected = line.split("==", 1)
            actual = metadata.version(name)
            pinned_count += 1
            if actual != expected:
                lock_mismatches.append({"package": name, "expected": expected, "actual": actual})
    result["local_dependency_lock"] = {"pinned_count": pinned_count,
                                       "mismatches": lock_mismatches}
    pip_check = subprocess.run([sys.executable, "-m", "pip", "check"],
                               text=True, capture_output=True)
    result["pip_check"] = {"returncode": pip_check.returncode,
                           "stdout": pip_check.stdout, "stderr": pip_check.stderr}
    result["passed"] = (all(c["passed"] for c in result["checks"])
        and result["artifact_unchanged"] and result["model_version_unchanged"]
        and result["version_consistency"] and not lock_mismatches and pip_check.returncode == 0)
    result["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["scope"] = ("15 real HTTP numeric-contract cases plus runtime version, artifact and "
                       "local dependency checks. No model training, notebook execution or load benchmark.")
    result["status"] = "PASS" if result["passed"] else "FAILED"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "passed": result["passed"],
                      "http_cases": len(result["checks"])}, ensure_ascii=False))
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON path; existing evidence is never overwritten")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or ROOT / "reports/release" / f"contract_check_{stamp}.json"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    marker = {"status": "RUNNING", "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat()}
    # Exclusive creation protects both released evidence and concurrent rechecks.
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(marker, indent=2) + "\n")
    try:
        return verify(output)
    except Exception as exc:
        marker.update(status="FAILED", ended_at_utc=datetime.now(timezone.utc).isoformat(),
                      error_type=type(exc).__name__, error=str(exc))
        output.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "passed": False,
                          "error_type": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
