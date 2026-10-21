# Local operations and recovery

## Start, inspect, stop

From the project directory after training:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 30
Invoke-RestMethod http://127.0.0.1:8011/ready
docker compose stop
docker compose start
```

The port is bound to 127.0.0.1. Only this machine can connect. Docker Desktop must be running. If port 8011 is occupied, edit the host side of the compose port mapping and pass the matching URL to the verification scripts. Do not terminate an unrelated process.

## Model lifecycle

The artifact is loaded once at startup. Record its SHA-256, model version, configuration and dataset hash together. The version identifies dataset/configuration/selected weight; the file SHA identifies exact serialized bytes. A valid restart must pass readiness before traffic is considered usable. Save a known-good model under ignored `artifacts/releases/` before trying another locally trained version.

```powershell
New-Item -ItemType Directory -Force artifacts\releases
Copy-Item -LiteralPath artifacts\model.joblib -Destination artifacts\releases\v0.1.0-model.joblib
Get-FileHash -Algorithm SHA256 artifacts\releases\v0.1.0-model.joblib
```

To roll back a later model, stop this project's service, copy the known-good local artifact to `artifacts/model.joblib`, start it and run `scripts/verify_live.py`. Do not overwrite or delete the candidate: retain it under a separate versioned path for diagnosis. This project verifies missing-model failure and recovery in an isolated second container; that is not a claim of a multi-version zero-downtime rollout.

## Endpoint contract

| Route | Meaning |
|---|---|
| `/health` | The process is alive; check the returned ready flag |
| `/ready` | 200 only when the model passed validation; otherwise 503 |
| `/model` | Version, protocol, dataset evaluation context |
| `/genres` | Accepted candidate category values |
| `/recommendations` | Bounded input, known-user BPR or cold fallback |
| `/metrics` | Per-process request/5xx counts and up to 10,000 recent durations |
| `/evidence` | Aggregate offline evaluation, separate from live serving |

Do not load another person's joblib/pickle file: loading it can execute code. The artifact is trusted because this project creates it locally. Shape/finite checks detect corruption but are not a sandbox for malicious artifacts. No secrets are needed for this local project. The dataset and model contain historical user interactions and are excluded from public source distribution.

## Interpreting load results

The script excludes 10 warm-up requests and verifies the warm user actually returns the personalized strategy. The measured mix is 75% user 1161 and 25% cold requests, K=10, on a single localhost connection pool with 8 client workers. P95 is measured from client request to response and includes HTTP and Docker overhead. It is not the same as the API's model-only `latency_ms`. CPU contention, OS, Docker and other workloads affect it; 500 requests do not establish maximum throughput or a reliability SLO.
