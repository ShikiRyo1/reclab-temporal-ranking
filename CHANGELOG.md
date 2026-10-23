# Changelog

## 0.1.2 — 2026-10-22

- Fixed implicit numeric coercion at the HTTP boundary: integer IDs/counts reject booleans, strings and integral floats; the optional finite weight rejects booleans/strings but accepts integer 0 and 1. Added 15 regression cases and passed the full 65-test suite.
- Rebuilt the local Docker service with package, API and image version 0.1.2; passed the original 17 real HTTP checks and 15 additional numeric-contract requests. Preserved the original 0.1.0 image, trained artifact, model version, training code and frozen evaluation reports.
- Independently rechecked data lineage, temporal evaluation and metric calculations from the existing model arrays. The eight upstream ranking matches were checked against historical executed notebooks and source hashes; this audit did not rerun notebook execution or model training. The historical 500-request load test was not repeated.
- Corrected stale P2 handoff wording and documented the strict input contract, build provenance and remaining single-seed/time-window limits. Release Git/remote evidence is recorded separately by the release audit.

## 0.1.1 — 2026-10-21

- Re-audited the 40 portfolio requirements and found five documentation/provenance gaps that the earlier all-pass wording missed. Added first-time setup guidance, implementation-specific complexity analysis and a direct line guide for the original upstream notebook cells.
- Preserved the original manuals and experiments. Re-ran 50 local tests and 17 real HTTP checks, and independently recomputed the temporal cohorts, four rankers, validation selection and paired bootstrap from raw data and frozen model arrays.
- Extended screenshot provenance and transfer records, explicitly retaining unknown historical capture/transfer times. Added contemporaneously timed browser replays. The companion builder now preserves extended screenshot metadata and refuses silent image-hash changes.
- This is a documentation and audit patch. Training code, trained artifact and the running 0.1.0 Docker image are unchanged; no additional training, cloud deployment or online uplift is claimed.

## 0.1.0 — 2026-10-21

- Reproduced the pinned upstream SAR and BPR notebooks on MovieLens 100K; all eight saved ranking metrics matched. Preserved upstream code and attribution.
- Added a separate full-catalog chronological MovieLens 1M experiment, training-only catalog statistics, validation-constrained novelty reranking and paired user bootstrap. Two complete frozen runs produced identical evaluation results.
- Delivered a typed FastAPI service, Chinese browser demo, cold-start fallback, metadata/artifact validation, report-to-model hash binding, health/readiness and bounded metrics.
- Built and ran a non-root Docker service. Verified 17 real HTTP checks, 500-request bounded local load and an isolated missing-model recovery exercise.
- Fixed artifact metadata and stale-report failure modes during independent review. Added early rejection of unsupported training protocol parameters. The final local suite contains 50 passing tests.
- Added Chinese-first teaching sources, editable mathematical explanations, code line references, real screenshots, career materials and recorded visual review.
- Kept GitHub Actions as an inactive template because the authenticated token lacks workflow scope. No public cloud deployment or online uplift is claimed.

## baseline-v1 — 2026-10-20

- Established the pinned upstream reproduction environment and initial baseline evidence.

Release artifacts distinguish upstream reproduction, this project's extension, local deployment and personal learning. A completed automated run does not certify the learner's independent mastery.
