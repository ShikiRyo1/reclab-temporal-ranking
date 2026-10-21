# Serving artifact contract

Artifact: artifacts/model.joblib (private local model, never load an untrusted joblib file). schema_version=1.

Public entry point: from reclab.models import recommend; recommend(artifact, user_id=None, k=10, novelty_weight=None, preferred_genres=None) returns a list of dictionaries with item_id, title, genres (list), score, base_score, popularity, is_long_tail, reason.

The list is unique and excludes every available observed training interaction, including low ratings. A user without a trained positive-feedback vector is a model-cold user and receives training-positive popularity fallback, optionally restricted to provided genres; that user can still have low-rating history to exclude. A None or completely unknown ID has no stored history. k is in [1,50]; novelty_weight in [0,1]. Invalid genre input raises ValueError rather than silently matching nothing. Empty candidate set returns []. API validates user IDs separately; IDs absent from the factor map are legitimate cold starts.

artifact keys: schema_version, model_version, dataset, trained_through_utc, protocol, config, user_ids (numpy), item_ids(numpy), user_index(dict), item_index(dict), user_factors, item_factors, item_biases, items(list of dict), seen_items(dict int -> list int), popularity_scores(numpy aligned to item_ids), long_tail_mask(numpy), selected_lambda, metrics_summary, training_positive_counts, cornac_version.

The current artifact has 4865 user vectors, 3444 item vectors and 64 factors. Both factor and serving-history cutoff are 2000-11-22T03:06:26+00:00. Offline test filtering additionally uses validation observations through 2000-12-10T04:20:42+00:00; static serving does not silently update that history. API startup validates metadata types, and the evidence endpoint is bound to the loaded artifact's SHA-256.

The frozen training/evaluation CLI supports only k=10 and positive_threshold=4, rejecting other values before data loading. The serving API supports exploratory k=1..50 requests, but published metrics remain @10. Changing API k does not create an evaluated metric for that k.

Items are only in the training-positive catalog. Scores are relative ranking scores, not predicted rating or confidence. Metadata and user training histories derive from MovieLens and stay in ignored local artifacts; the public repository contains code, aggregate metrics, download scripts and synthetic test fixtures. Do not publish raw user histories or source dataset.
