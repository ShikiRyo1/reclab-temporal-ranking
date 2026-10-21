"""Exercise real HTTP boundaries and artifact failure behavior on tiny fixtures."""
import joblib
import hashlib
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient

from reclab.api import create_app, validate_artifact
import reclab.api as api


@pytest.fixture
def artifact():
    return {
        "schema_version": 1, "model_version": "fixture-v1",
        "user_ids": np.array([1]), "item_ids": np.array([10, 20, 30]),
        "user_factors": np.array([[1.0, 0.0]]),
        "item_factors": np.array([[1.0, 0.0], [0.7, 0.3], [0.2, 0.8]]),
        "items": [{"item_id": 10, "title": "Seen", "genres": ["Drama"]},
                  {"item_id": 20, "title": "Second", "genres": ["Comedy"]},
                  {"item_id": 30, "title": "Third", "genres": ["Drama"]}],
        "user_index": {1: 0}, "item_index": {10: 0, 20: 1, 30: 2},
        "item_biases": np.zeros(3), "long_tail_mask": np.array([False, True, True]),
        "seen_items": {1: [10]}, "popularity_scores": np.array([3., 2., 1.]),
        "selected_lambda": 0.0, "protocol": {"dataset": "synthetic test only"},
        "metrics_summary": {}
    }


@pytest.fixture
def client(tmp_path, artifact):
    path = tmp_path / "model.joblib"
    joblib.dump(artifact, path)
    with TestClient(create_app(path)) as c:
        yield c


def test_liveness_is_not_readiness(tmp_path):
    with TestClient(create_app(tmp_path / "missing.joblib")) as c:
        assert c.get("/health").json() == {"status": "alive", "ready": False}
        assert c.get("/ready").status_code == 503
        assert c.post("/recommendations", json={}).status_code == 503


def test_corrupt_artifact_never_becomes_ready(tmp_path):
    path = tmp_path / "bad.joblib"
    path.write_bytes(b"not a serialized model")
    with TestClient(create_app(path)) as c:
        assert c.get("/ready").status_code == 503


@pytest.mark.parametrize("payload", [
    {"k": 0}, {"k": 51}, {"user_id": -1}, {"novelty_weight": -0.1},
    {"novelty_weight": 1.1}, {"user": 1}, {"preferred_genres": ["NotAGenre"]},
])
def test_bad_requests_are_rejected(client, payload):
    assert client.post("/recommendations", json=payload).status_code == 422


def test_version_and_fallback_are_visible(client):
    r = client.post("/recommendations", json={"user_id": 99999, "k": 2})
    assert r.status_code == 200
    assert r.json()["strategy"] == "cold_start_popularity"
    assert r.json()["model_version"] == "fixture-v1"
    assert r.json()["returned_k"] == 2


def test_seen_items_are_not_recommended(client):
    data = client.post("/recommendations", json={"user_id": 1, "k": 3}).json()
    assert 10 not in [r["item_id"] for r in data["recommendations"]]
    assert data["returned_k"] == 2


def test_genre_filter_and_finite_scores(client):
    r = client.post("/recommendations", json={"preferred_genres": ["Drama"], "k": 5})
    assert r.status_code == 200
    rows = r.json()["recommendations"]
    assert rows
    assert all("Drama" in row["genres"] for row in rows)
    assert all(np.isfinite(row["score"]) for row in rows)


def test_repeat_request_is_deterministic(client):
    a = client.post("/recommendations", json={"user_id": 1}).json()
    b = client.post("/recommendations", json={"user_id": 1}).json()
    assert a["recommendations"] == b["recommendations"]


def test_observability_and_home(client):
    assert client.get("/").status_code == 200
    assert client.get("/ready").json()["status"] == "ready"
    metrics = client.get("/metrics").json()
    assert metrics["requests_total"] >= 2
    assert metrics["latency_p95_ms"] is not None
    assert metrics["server_failures_total"] == 0


def test_wrong_factor_dimensions_fail_validation(artifact):
    artifact["item_factors"] = np.zeros((3, 5))
    with pytest.raises(ValueError, match="dimensions"):
        validate_artifact(artifact)


def test_nonfinite_factors_fail_validation(artifact):
    artifact["item_factors"][0, 0] = np.nan
    with pytest.raises(ValueError, match="Non-finite"):
        validate_artifact(artifact)


def test_tampered_schema_fails_validation(artifact):
    artifact["schema_version"] = 999
    with pytest.raises(ValueError, match="schema"):
        validate_artifact(artifact)


@pytest.mark.parametrize("field,value", [("genres", "Drama|Comedy"), ("title", None)])
def test_invalid_metadata_fails_readiness(tmp_path, artifact, field, value):
    artifact["items"][0][field] = value
    path = tmp_path / "invalid_metadata.joblib"
    joblib.dump(artifact, path)
    with TestClient(create_app(path)) as c:
        assert c.get("/ready").status_code == 503


def test_evidence_is_bound_to_loaded_artifact(tmp_path, artifact, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
    path = tmp_path / "model.joblib"
    joblib.dump(artifact, path)
    report = tmp_path / "reports/experiment/summary.json"
    report.parent.mkdir(parents=True)
    with TestClient(create_app(path)) as c:
        report.write_text(json.dumps({"artifact": {"sha256": "wrong"}}))
        assert c.get("/evidence").status_code == 409
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        report.write_text(json.dumps({"artifact": {"sha256": digest}}))
        assert c.get("/evidence").status_code == 200
        assert c.get("/ready").json()["artifact_sha256"] == digest
