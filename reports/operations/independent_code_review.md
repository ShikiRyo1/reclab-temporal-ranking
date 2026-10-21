# Independent review of serving and deployment code

Review date: 2026-10-21 UTC. Reviewer: the model/evaluation subagent, independently of the API/deployment author. Scope: `src/reclab/api.py`, `scripts/benchmark_api.py`, `scripts/verify_live.py`, `Dockerfile`, `compose.yaml`, `tests/test_api.py`; supporting reads included `pyproject.toml`, `requirements-api.txt`, `.dockerignore` and the actual local experiment/operation reports. No root-owned source file was edited by this reviewer.

## Findings and disposition

### Fixed: readiness accepted metadata that could not be served

Before correction, changing every item's `genres` from a list to a pipe-separated string, or setting titles to `None`, still passed the API artifact validator and returned HTTP 200 from `/ready`. Actual `POST /recommendations` calls returned HTTP 500. The genre path disagreed with both the core recommender's list convention and the response schema; null titles violated the string response schema.

This was reproduced with copies of the actual artifact written to a temporary directory and `TestClient(..., raise_server_exceptions=False)`. The original artifact was not modified. Priority: P2, because the advertised startup schema validation did not establish serviceability for these structurally malformed artifacts. The current valid production-demo artifact was unaffected.

The API author now enforces nonempty string titles and lists of nonempty genre strings at startup, and removed string-genre handling that implied unsupported compatibility. Two new parameterized tests confirm invalid metadata keeps `/ready` at HTTP 503. The reviewer re-read the fix and reran the entire API test file successfully.

### Fixed: experiment evidence was not bound to the loaded model

Before correction, `/evidence` returned a fixed summary file without checking which artifact it described. A model replacement could therefore show a prior model's experiment results. The live verifier checked the MovieLens row count but not that the report described the served artifact. Priority: P2; this affected the audit trail after a model change, even though the artifacts in the current successful run matched.

The API author now computes the trusted artifact's SHA-256 at startup, exposes it through `/ready` and `/model`, and returns HTTP 409 when the summary's artifact digest differs. The live verifier compares the HTTP digest and report digest with the actual local artifact bytes. A new test deliberately supplies a mismatched digest, observes HTTP 409, then supplies the matching digest and observes HTTP 200. The reviewer read the implementation and reran that test within the passing API suite.

### Fixed: live verifier failure did not leave a machine-readable result

Previously, an unavailable service or unexpected readiness/report response could raise an exception before writing a verification report. The CLI now catches verification exceptions, writes `passed: false` with exception type and detail, and exits nonzero. The reviewer actually ran the CLI against the intentionally unavailable loopback endpoint `http://127.0.0.1:1`: it wrote failure JSON, recorded `ConnectError`, and exited 1. The temporary report was not used as success evidence.

### Fixed: workload description did not expose exact cohort counts

The original benchmark repeated one known user for three requests out of four and used `None` for the fourth. Ten unmeasured warmups checked the known-user strategy. Its original “75% / 25%” text was exact for the actual 500-request run, but would be rounded for arbitrary request counts; measured requests also lacked a direct strategy assertion.

The benchmark now records `known_requests` and `cold_requests`, describes the exact repeating pattern, and validates the expected strategy on every measured response. No fabricated workload was found. The original 500-request report represented 375 known-user requests and 125 cold-start requests, with ten warmups excluded. This remains a narrow, single-known-user, closed-loop localhost workload, as its report states; it is not a population traffic sample, production SLO, or maximum capacity measurement.

## Deployment-path review

- Docker installs the package containing `reclab/web/index.html`; `WEB` resolves relative to the installed module. Package-data configuration includes the HTML file.
- `/models/model.joblib` is supplied by the read-only Compose mount and is the configured model path. `/app/reports/experiment` is the read-only report mount; `RECLAB_PROJECT_ROOT=/app` makes the API evidence path resolve there.
- The image creates a non-root application user and switches to it. The healthcheck calls the actual `/ready` endpoint. Compose binds the service to localhost only.
- `.dockerignore` uses an allowlist for source and build metadata, excluding raw MovieLens data, local environments and model artifacts from the build context. The artifact is mounted at runtime instead of embedded into a redistributed image.
- Core inference does not import Cornac at module scope, and the API dependency file excludes it. Training and serving dependency scopes agree.

No substantive path or packaging defect was found within the reviewed local Docker workflow. Existing successful HTTP parity reports are real-request evidence, separate from this source review. The API author is rebuilding and rerunning deployment verification after the fixes; this report does not silently treat an older container as proof of the corrected source.

## Reviewer-run verification

1. Before fixes: the existing API suite passed 17 tests, but the two malformed-artifact probes reproduced the readiness/HTTP-500 defect above.
2. After fixes: `.venv/Scripts/python.exe -m pytest tests/test_api.py -q --junitxml=reports/operations/independent_api_tests.xml` passed **20 tests** in 1.73 seconds. One installed Starlette/httpx deprecation warning remains; it did not fail requests or assertions.
3. After fixes: intentionally unavailable endpoint verification produced failure JSON and exit status 1 as described above.
4. No model training or parameter selection was repeated for this review. The model experiment's own 26 tests and temporal metrics are separate evidence.

Within this reviewed scope, both P2 findings and the two diagnostic/workload clarity issues have been corrected and checked. This is a bounded local-demo review, not a claim that internet-scale operations, authentication, online learning, data drift, or arbitrary hostile model uploads have been implemented or validated.
