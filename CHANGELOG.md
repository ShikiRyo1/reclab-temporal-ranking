# Changelog

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
