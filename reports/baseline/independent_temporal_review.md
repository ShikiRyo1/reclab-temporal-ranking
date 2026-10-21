# Independent temporal implementation review

Scope: read-only review of src/reclab/data.py, metrics.py, models.py, rerank.py, train.py, configs/temporal_1m.json and reports/experiment/protocol.md. The reviewer implemented the separate upstream baseline, not these temporal models. No retraining or edits to the temporal implementation were performed during this review.

## Result

No correctness issue was found that invalidates the reported current configuration (rating threshold 4, K=10, seed 42, one thread). This is a scoped source review, not a proof that all future configurations are supported.

| Area | Checked behavior |
|---|---|
| Time split | Global cutoffs at 70% and 85% row positions; equal timestamps stay together; validation and test are strictly later |
| Train-only catalog | Item catalog, user factors, popularity counts and long-tail definitions derive only from training positives |
| Labels | Training and current evaluation both use rating >= 4; missing ratings are not interpreted as demonstrated dislike |
| Seen filtering | Validation excludes all training ratings, including low ratings; test excludes all train+validation ratings |
| Denominators | Relevant targets require eligible catalog and not-seen status; exclusions and users lacking eligible targets are explicitly counted |
| Fair comparison | Popularity, SAR-style and BPR share candidate item IDs and history masks; custom SAR-style is accurately distinguished from upstream SAR |
| ID mapping | Cornac encounter-order IDs are explicitly reordered to artifact IDs before scoring |
| Metrics | Binary NDCG ideal denominator uses min(K, number of eligible positives); recall divides by the eligible positive count; averages are per user |
| Cold users | Separate cohort with the same popularity fallback across methods; no fabricated personalized scores |
| Selection | Reranking weight is selected only on validation, under a 98% baseline NDCG constraint, then written and hashed before test evaluation |
| Reranking | Train-only novelty is mixed within base top100; zero weight preserves the full-precision base order; ties have explicit item-ID ordering |
| Uncertainty | Per-user paired differences are aligned before user bootstrap; no claim of uncertainty across training seeds or time periods |
| Serving distinction | Frozen training snapshot history differs from the later test-history mask; artifact metadata and protocol disclose this limitation |

## Future-configuration guardrails

Two low-impact risks were sent to the modeling owner; they do not change the current reported results:

1. evaluate accepts K but report keys are named ndcg_at_10/recall_at_10. If K is changed without validation, the labels become misleading.
2. Training reads positive_threshold from config, while evaluation's eligible_targets default is 4. Changing the config threshold alone would change only training labels.

Resolution verified in the updated train.run: immediately after reading config and before reading data, the entrypoint now rejects K != 10 or positive_threshold != 4. The modeling owner reported four parameterized regression cases and 50 passing tests. The reviewer inspected the guards directly; the current default experiment did not need retraining. Configuration bpr.num_threads is recorded, but fit_rankers intentionally supplies num_threads=1; this fixed experiment uses one thread.

## Evidence boundaries

The time cutoffs are chosen retrospectively from dataset timestamp quantiles. That defines a reproducible historical holdout; it is not evidence that a live system knew in advance what timestamp would contain exactly 70% of all eventual ratings. The model is frozen at the first cutoff; test history advances to the second. This design is internally consistent and explicitly documented.

The novelty extension trades relevance for exposure in the reported test. These metrics do not establish user satisfaction, revenue, fairness or causal uplift. The code and protocol correctly preserve those distinctions.
