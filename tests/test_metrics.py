import numpy as np
import pandas as pd
import pytest

from reclab.metrics import bootstrap_interval, paired_comparison, ranking_metrics


def test_binary_ndcg_and_recall_match_hand_calculation():
    result = ranking_metrics([1, 2, 3], {1, 3}, k=3)
    assert result["ndcg"] == pytest.approx(1.5 / (1 + 1 / np.log2(3)))
    assert result["recall"] == 1


def test_unreturned_relevant_items_stay_in_recall_denominator():
    assert ranking_metrics([1], {1, 2, 3}, k=10)["recall"] == pytest.approx(1 / 3)


def test_invalid_truth_and_duplicate_recommendations_are_rejected():
    with pytest.raises(ValueError):
        ranking_metrics([1], set())
    with pytest.raises(ValueError):
        ranking_metrics([1, 1], {1})


def test_bootstrap_is_deterministic_and_constant_sample_is_exact():
    assert bootstrap_interval(np.ones(5), 100) == [1, 1]
    values = np.arange(10) / 10
    assert bootstrap_interval(values, 100) == bootstrap_interval(values, 100)


def test_paired_comparison_aligns_user_ids_and_rejects_changed_cohort():
    base = pd.DataFrame({"user_id": [1, 2], "cohort": ["warm", "warm"],
                         "ndcg": [.2, .5], "recall": [.1, .3], "tail_exposure": [.1, .2]})
    changed = base.iloc[::-1].copy()
    changed["ndcg"] += .1
    result = paired_comparison(base, changed, 100)
    assert result["ndcg"]["mean_difference"] == pytest.approx(.1)
    with pytest.raises(ValueError, match="identical"):
        paired_comparison(base, changed.iloc[:1], 100)
