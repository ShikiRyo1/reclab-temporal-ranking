"""Compare the deployed HTTP service with the trusted local artifact."""
import argparse
import hashlib
import json
from pathlib import Path

import httpx
import joblib

from reclab.models import recommend


def verify(url, artifact_path):
    artifact = joblib.load(artifact_path)  # Only this project's own artifact is trusted.
    digest = hashlib.sha256(Path(artifact_path).read_bytes()).hexdigest()
    user = int(artifact["user_ids"][0])
    checks = {}
    with httpx.Client(base_url=url, timeout=30) as client:
        ready = client.get("/ready")
        checks["ready"] = ready.status_code == 200
        checks["version_matches_artifact"] = ready.json()["model_version"] == artifact["model_version"]
        checks["artifact_bytes_match"] = ready.json()["artifact_sha256"] == digest
        checks["home"] = client.get("/").status_code == 200
        checks["openapi"] = client.get("/openapi.json").status_code == 200
        evidence = client.get("/evidence")
        evidence.raise_for_status()
        checks["evidence"] = evidence.json()["data"]["rows"] == 1000209
        checks["evidence_artifact_matches"] = evidence.json()["artifact"]["sha256"] == digest
        for label, payload in (
            ("known", {"user_id": user, "k": 10}),
            ("cold", {"user_id": None, "k": 10}),
            ("genre", {"user_id": user, "k": 10, "preferred_genres": ["Drama"]}),
            ("raw_bpr", {"user_id": user, "k": 10, "novelty_weight": 0}),
        ):
            response = client.post("/recommendations", json=payload)
            response.raise_for_status()
            actual = response.json()["recommendations"]
            expected = recommend(artifact, **payload)
            # BLAS implementations can vary in last-bit scores across OS platforms.
            checks[f"{label}_ranking_matches"] = ([r["item_id"] for r in actual] ==
                                                   [r["item_id"] for r in expected])
            checks[f"{label}_unique"] = len({r["item_id"] for r in actual}) == len(actual)
        invalid = client.post("/recommendations", json={"k": 51})
        checks["bad_request_422"] = invalid.status_code == 422
        checks["metrics"] = client.get("/metrics").json()["requests_total"] > 0
    return {"base_url": url, "model_version": artifact["model_version"],
            "warm_user": user, "checks": checks, "passed": all(checks.values()),
            "scope": "Real HTTP requests to the local Docker service; ranking parity with native Python"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--artifact", default="artifacts/model.joblib")
    parser.add_argument("--output", default="reports/operations/live_verification.json")
    args = parser.parse_args()
    try:
        result = verify(args.url, args.artifact)
    except Exception as exc:
        result = {"base_url": args.url, "passed": False, "error_type": type(exc).__name__,
                  "error": str(exc)}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
