"""Measure actual HTTP response latency on a fixed, recorded request workload."""
import argparse
import concurrent.futures
import json
import platform
import time
from pathlib import Path

import httpx
import numpy as np


def run(base_url, requests, concurrency, warm_user):
    """Do not include startup or warm-up requests in the measured steady-state run."""
    with httpx.Client(base_url=base_url, timeout=30) as client:
        ready = client.get("/ready")
        ready.raise_for_status()
        model = ready.json()
        for _ in range(10):
            probe = client.post("/recommendations", json={"user_id": warm_user, "k": 10})
            probe.raise_for_status()
            if probe.json()["strategy"] != "personalized_bpr":
                raise ValueError("warm-user must be present in the trained model")

        def request(i):
            payload = {"user_id": warm_user if i % 4 else None, "k": 10}
            started = time.perf_counter()
            try:
                r = client.post("/recommendations", json=payload)
                data = r.json()
                expected_strategy = "personalized_bpr" if i % 4 else "cold_start_popularity"
                valid = (r.status_code == 200 and data.get("returned_k", 0) > 0
                         and data.get("strategy") == expected_strategy)
                return (time.perf_counter() - started) * 1000, valid, r.status_code
            except Exception as exc:
                return (time.perf_counter() - started) * 1000, False, type(exc).__name__

        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            records = list(pool.map(request, range(requests)))
        wall = time.perf_counter() - started
    latency = [r[0] for r in records]
    errors = [r for r in records if not r[1]]
    return {"requests": requests, "concurrency": concurrency,
            "wall_seconds": wall, "throughput_requests_per_second": requests / wall,
            "p50_ms": float(np.percentile(latency, 50)),
            "p95_ms": float(np.percentile(latency, 95)),
            "p99_ms": float(np.percentile(latency, 99)),
            "max_ms": max(latency), "errors": len(errors),
            "error_samples": errors[:5], "model": model,
            "known_requests": sum(i % 4 != 0 for i in range(requests)),
            "cold_requests": sum(i % 4 == 0 for i in range(requests)),
            "workload": f"3 of each 4 requests use known user_id={warm_user}; others cold; k=10; 10 warmups excluded",
            "scope": "Localhost closed-loop client; not production SLO or maximum capacity",
            "client_platform": platform.platform()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--warm-user", type=int, default=1161)
    parser.add_argument("--output", default="reports/operations/load_test.json")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    result = run(args.url, args.requests, args.concurrency, args.warm_user)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise SystemExit(1)
