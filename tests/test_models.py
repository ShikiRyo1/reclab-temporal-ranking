import copy

import numpy as np
import pandas as pd
import pytest

from reclab.models import fit_rankers, recommend, validate_artifact


def artifact():
    return {
        "schema_version": 1, "model_version": "fixture",
        "user_ids": np.array([7]), "item_ids": np.array([11, 12, 13]),
        "user_index": {7: 0}, "item_index": {11: 0, 12: 1, 13: 2},
        "user_factors": np.array([[1., 0.]]),
        "item_factors": np.array([[100., 0.], [3., 0.], [2., 0.]]),
        "item_biases": np.array([0., 0., 5.]),
        "items": [{"item_id": i, "title": str(i), "genres": ["Drama"] if i != 12 else ["Comedy"]}
                  for i in [11, 12, 13]],
        "seen_items": {7: [11]}, "popularity_scores": np.array([1., 100., 10.]),
        "long_tail_mask": np.array([True, False, True]), "selected_lambda": 0.,
    }


def test_known_user_excludes_seen_and_includes_item_bias():
    result = recommend(artifact(), 7, 3)
    assert [row["item_id"] for row in result] == [13, 12]
    assert result[0]["base_score"] == 7.
    assert result[0]["reason"] == "personalized_bpr"


def test_unknown_user_fallback_and_genre_filter():
    result = recommend(artifact(), 999, 3, preferred_genres=["Drama"])
    assert [row["item_id"] for row in result] == [13, 11]
    assert all(row["reason"] == "cold_start_popularity" for row in result)


def test_unknown_genre_and_bad_weight_rejected():
    with pytest.raises(ValueError, match="Unknown genre"):
        recommend(artifact(), 7, preferred_genres=["Invalid"])
    with pytest.raises(ValueError):
        recommend(artifact(), 7, novelty_weight=np.nan)


def test_readiness_detects_invalid_dimensions_and_nonfinite_factors():
    good = artifact()
    assert validate_artifact(good) == {"users": 1, "items": 3, "factors": 2}
    bad = copy.deepcopy(good)
    bad["item_biases"] = np.zeros(2)
    with pytest.raises(ValueError):
        validate_artifact(bad)
    bad = copy.deepcopy(good)
    bad["user_factors"][0, 0] = np.inf
    with pytest.raises(ValueError):
        validate_artifact(bad)


def test_small_real_bpr_fit_preserves_id_alignment():
    frame = pd.DataFrame({
        "user_id": [9, 9, 2, 2, 4, 4], "item_id": [33, 11, 11, 22, 22, 33],
        "rating": [5, 4, 4, 5, 5, 4], "timestamp": [1, 2, 3, 4, 5, 6],
    })
    config = {"positive_threshold": 4, "seed": 42,
              "bpr": {"factors": 4, "epochs": 2, "learning_rate": .01,
                      "lambda_reg": .01, "use_bias": True}}
    model, scores = fit_rankers(frame, config)
    assert list(model["user_ids"]) == [2, 4, 9]
    assert list(model["item_ids"]) == [11, 22, 33]
    assert np.allclose(scores["bpr"], model["user_factors"] @ model["item_factors"].T
                       + model["item_biases"])
    assert np.allclose(scores["popularity"], [2, 2, 2])


def test_readiness_rejects_silent_id_or_title_misalignment():
    bad = artifact()
    bad["item_index"] = {11: 1, 12: 0, 13: 2}
    with pytest.raises(ValueError, match="ID mapping"):
        validate_artifact(bad)
    bad = artifact()
    bad["items"][0]["item_id"] = 99
    with pytest.raises(ValueError, match="metadata order"):
        validate_artifact(bad)


def test_documented_bpr_triplet_gradient_matches_finite_difference():
    parameters = np.array([.2, .3, .4, .1, .1, .2, .05, -.02])
    regularization = .01

    def loss(theta):
        gap = theta[:2] @ (theta[2:4] - theta[4:6]) + theta[6] - theta[7]
        return np.logaddexp(0, -gap) + .5 * regularization * (theta @ theta)

    u, positive, negative = parameters[:2], parameters[2:4], parameters[4:6]
    gap = u @ (positive - negative) + parameters[6] - parameters[7]
    q = 1 / (1 + np.exp(gap))
    analytic = np.r_[-q * (positive - negative), -q * u, q * u, -q, q]
    analytic += regularization * parameters
    h = 1e-6
    numeric = np.array([(loss(parameters + h * e) - loss(parameters - h * e)) / (2 * h)
                        for e in np.eye(len(parameters))])
    assert np.allclose(analytic, numeric, atol=1e-8, rtol=1e-7)
