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

The delivered release already has a local snapshot in `artifacts/releases/v0.1.0/`: model, matching aggregate summary, training configuration and selected configuration. Hashes are recorded in `reports/release/local_model_snapshot.json`. The snippet above shows a separate manual backup, which is optional.

To roll back a later model, retain the candidate under a separate versioned path, stop this project's service, restore the known-good artifact to `artifacts/model.joblib` **and its matching summary to `reports/experiment/summary.json`**, start it and run `scripts/verify_live.py`. Restoring only the artifact can correctly trigger `/evidence` HTTP 409 if the summary describes another model. This project verifies missing-model failure and recovery in an isolated second container; that is not a claim of a multi-version zero-downtime rollout.

## Endpoint contract

| Route | Meaning |
|---|---|
| `/health` | The process is alive; check the returned ready flag |
| `/ready` | 200 only when the model passed validation; otherwise 503 |
| `/model` | Version, protocol, dataset evaluation context |
| `/genres` | Accepted candidate category values |
| `/recommendations` | Bounded input, known-user BPR or cold fallback |
| `/metrics` | Per-process request/5xx counts and up to 10,000 recent durations |
| `/evidence` | Aggregate offline evaluation; HTTP 409 if its artifact hash differs from the loaded model |

Do not load another person's joblib/pickle file: loading it can execute code. The artifact is trusted because this project creates it locally. Shape/finite checks detect corruption but are not a sandbox for malicious artifacts. No secrets are needed for this local project. The dataset and model contain historical user interactions and are excluded from public source distribution.

The initial review found two failure paths and fixed them before release: malformed title/genre metadata is rejected before readiness, and `/evidence` is bound to the loaded artifact's SHA-256 instead of blindly serving a stale report. Regression tests exercise both cases.

GitHub Actions remains inactive because the authenticated OAuth token lacks the required workflow scope. `docs/ci-template.yml` is reviewable source only; no GitHub CI success is claimed. This does not affect the local executed tests, Docker image or API.

## Interpreting load results

The script excludes 10 warm-up requests and verifies the warm user actually returns the personalized strategy. The measured mix is 75% user 1161 and 25% cold requests, K=10, on a single localhost connection pool with 8 client workers. P95 is measured from client request to response and includes HTTP and Docker overhead. It is not the same as the API's model-only `latency_ms`. CPU contention, OS, Docker and other workloads affect it; 500 requests do not establish maximum throughput or a reliability SLO.
