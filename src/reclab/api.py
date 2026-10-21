"""Serve one trusted, immutable recommendation artifact with observable requests."""
from __future__ import annotations

import json
import hashlib
import logging
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from reclab.models import recommend, validate_artifact as validate_model

LOGGER = logging.getLogger("reclab.api")
ROOT = Path(os.environ.get("RECLAB_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
WEB = Path(__file__).with_name("web")


class RecommendationRequest(BaseModel):
    """Bound request size and reject silently misspelled input fields."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [{"user_id": 1161, "k": 10, "preferred_genres": [], "novelty_weight": None}]})
    user_id: int | None = Field(default=None, ge=1)
    k: int = Field(default=10, ge=1, le=50)
    preferred_genres: list[str] = Field(default_factory=list, max_length=5)
    novelty_weight: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class RecommendedItem(BaseModel):
    """Expose score meaning and metadata through the generated OpenAPI schema."""
    item_id: int
    title: str
    genres: list[str]
    score: float = Field(allow_inf_nan=False, description="Relative ranking score, not probability")
    base_score: float = Field(allow_inf_nan=False)
    popularity: int
    is_long_tail: bool
    reason: str


class RecommendationResponse(BaseModel):
    model_version: str
    strategy: str
    requested_k: int
    returned_k: int
    novelty_weight: float
    requested_novelty_weight: float
    latency_ms: float
    recommendations: list[RecommendedItem]
    scope: str


def validate_artifact(artifact: dict[str, Any]) -> None:
    """Fail readiness before serving corrupt or structurally incompatible weights."""
    validate_model(artifact)
    required = {"schema_version", "model_version", "items", "user_ids", "item_ids",
                "user_factors", "item_factors", "seen_items", "popularity_scores",
                "selected_lambda"}
    missing = required - artifact.keys()
    if missing:
        raise ValueError(f"Artifact is missing required fields: {sorted(missing)}")
    if str(artifact["schema_version"]) not in {"1", "1.0", "1.0.0"}:
        raise ValueError("Unsupported artifact schema_version")
    users, items = np.asarray(artifact["user_ids"]), np.asarray(artifact["item_ids"])
    uf, itf = np.asarray(artifact["user_factors"]), np.asarray(artifact["item_factors"])
    if uf.ndim != 2 or itf.ndim != 2 or uf.shape[1] != itf.shape[1]:
        raise ValueError("User and item factors have incompatible dimensions")
    if uf.shape[0] != len(users) or itf.shape[0] != len(items):
        raise ValueError("Factor rows do not match the ID maps")
    if len(set(users.tolist())) != len(users) or len(set(items.tolist())) != len(items):
        raise ValueError("Duplicate IDs in artifact maps")
    if not np.isfinite(uf).all() or not np.isfinite(itf).all():
        raise ValueError("Model factors contain NaN or infinity")
    pop = np.asarray(artifact["popularity_scores"])
    if pop.shape != (len(items),) or not np.isfinite(pop).all():
        raise ValueError("Invalid popularity vector")
    if not 0 <= float(artifact["selected_lambda"]) <= 1:
        raise ValueError("Invalid selected reranking weight")
    if not all({"title", "genres", "item_id"}.issubset(item) for item in artifact["items"]):
        raise ValueError("Item metadata must contain title and genres")
    for item in artifact["items"]:
        if not isinstance(item["title"], str) or not item["title"].strip():
            raise ValueError("Item title must be a nonempty string")
        if not isinstance(item["genres"], list) or not all(
            isinstance(genre, str) and genre.strip() for genre in item["genres"]
        ):
            raise ValueError("Item genres must be a list of nonempty strings")


def create_app(model_path: str | Path | None = None) -> FastAPI:
    """Load the model once; process restart chooses another trusted version."""
    path = Path(model_path or os.environ.get("RECLAB_MODEL_PATH", ROOT / "artifacts/model.joblib"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.artifact = None
        app.state.load_error = None
        app.state.artifact_sha256 = None
        app.state.lock = threading.Lock()
        app.state.requests_total = 0
        app.state.failures_total = 0
        app.state.latencies = deque(maxlen=10000)
        app.state.started_at = time.time()
        try:
            # joblib uses pickle: only load an artifact created by this project.
            artifact = joblib.load(path)
            validate_artifact(artifact)
            app.state.artifact = artifact
            app.state.artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception as exc:
            app.state.load_error = type(exc).__name__
            LOGGER.exception("Model loading failed; readiness will return HTTP 503")
        yield

    app = FastAPI(title="Recommendation Lab", version="0.1.0", lifespan=lifespan,
                  description="Temporal recommendation research, cold-start fallback and controlled reranking.")

    @app.middleware("http")
    async def measure(request: Request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            if hasattr(app.state, "lock"):
                with app.state.lock:
                    app.state.requests_total += 1
                    app.state.failures_total += int(status >= 500)
                    app.state.latencies.append((time.perf_counter() - started) * 1000)

    def loaded():
        if app.state.artifact is None:
            raise HTTPException(503, "Model unavailable; inspect server startup logs")
        return app.state.artifact

    @app.get("/health")
    def health():
        return {"status": "alive", "ready": app.state.artifact is not None}

    @app.get("/ready")
    def ready():
        a = loaded()
        return {"status": "ready", "model_version": a["model_version"],
                "artifact_sha256": app.state.artifact_sha256,
                "schema_version": a["schema_version"], "n_users": len(a["user_ids"]),
                "n_items": len(a["item_ids"])}

    @app.get("/model")
    def model_info():
        a = loaded()
        return {"model_version": a["model_version"], "schema_version": a["schema_version"],
                "artifact_sha256": app.state.artifact_sha256,
                "n_users": len(a["user_ids"]), "n_items": len(a["item_ids"]),
                "selected_lambda": float(a["selected_lambda"]),
                "protocol": a.get("protocol", {}),
                "metrics_summary": a.get("metrics_summary", {}),
                "notice": "Offline benchmark. Ratings are not exposure logs or proven business lift."}

    @app.get("/genres")
    def genres():
        values = [item["genres"] for item in loaded()["items"]]
        unique = set()
        for value in values:
            unique.update(value)
        return {"genres": sorted(unique)}

    @app.post("/recommendations", response_model=RecommendationResponse)
    def recommendations(payload: RecommendationRequest):
        a = loaded()
        valid_genres = set(genres()["genres"])
        if not set(payload.preferred_genres).issubset(valid_genres):
            raise HTTPException(422, "Unknown genre; use GET /genres for valid values")
        started = time.perf_counter()
        rows = recommend(a, payload.user_id, k=payload.k,
                         novelty_weight=payload.novelty_weight,
                         preferred_genres=payload.preferred_genres or None)
        known = payload.user_id is not None and payload.user_id in a["user_index"]
        requested_weight = float(a["selected_lambda"] if payload.novelty_weight is None
                                 else payload.novelty_weight)
        return {"model_version": a["model_version"],
                "strategy": "personalized_bpr" if known else "cold_start_popularity",
                "requested_k": payload.k, "returned_k": len(rows),
                "novelty_weight": requested_weight if known else 0.0,
                "requested_novelty_weight": requested_weight,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "recommendations": rows,
                "scope": "Offline research demonstration; scores are not probabilities."}

    @app.get("/metrics")
    def metrics():
        with app.state.lock:
            samples = list(app.state.latencies)
            count, failures = app.state.requests_total, app.state.failures_total
        return {"requests_total": count, "server_failures_total": failures,
                "latency_sample_size": len(samples),
                "rolling_window_limit": 10000,
                "latency_p50_ms": float(np.percentile(samples, 50)) if samples else None,
                "latency_p95_ms": float(np.percentile(samples, 95)) if samples else None,
                "uptime_seconds": round(time.time() - app.state.started_at, 1)}

    @app.get("/evidence")
    def evidence():
        loaded()
        report = ROOT / "reports/experiment/summary.json"
        if not report.exists():
            return {"status": "pending", "message": "Run the experiment CLI to create the evaluation report."}
        summary = json.loads(report.read_text(encoding="utf-8-sig"))
        if summary.get("artifact", {}).get("sha256") != app.state.artifact_sha256:
            raise HTTPException(409, "Evaluation report belongs to a different model artifact")
        return summary

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(WEB / "index.html")

    return app


app = create_app()
