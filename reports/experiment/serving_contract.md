# Serving artifact contract

Artifact: artifacts/model.joblib (private local model, never load an untrusted joblib file). schema_version=1.

Public entry point: from reclab.models import recommend; recommend(artifact, user_id=None, k=10, novelty_weight=None, preferred_genres=None) returns a list of dictionaries with item_id, title, genres (list), score, base_score, popularity, is_long_tail, reason.

The list is unique and excludes all observed training interactions for known users, including low ratings. Unknown/None user uses training-positive popularity fallback, optionally restricted to provided genres. k is in [1,50]; novelty_weight in [0,1]. Invalid genre input raises ValueError rather than silently matching nothing. Empty candidate set returns []. API should validate user IDs separately; IDs absent from artifact are legitimate cold starts.

artifact keys: schema_version, model_version, dataset, trained_through_utc, config, user_ids (numpy), item_ids(numpy), user_index(dict), item_index(dict), user_factors, item_factors, item_biases, items(list of dict), seen_items(dict int -> list int), popularity_scores(numpy aligned to item_ids), long_tail_mask(numpy), selected_lambda, metrics_summary.

Items are only in the training-positive catalog. Scores are relative ranking scores, not predicted rating or confidence. metadata and user training histories derive from MovieLens and stay in ignored local artifacts; public repo ships code, aggregate metrics, download scripts and synthetic demo artifacts only, as decided by root. Do not publish raw user histories or source dataset.
