import numpy as np
import pytest

from reclab.rerank import novelty_scores, rank_topk, rerank


def test_ties_are_broken_by_item_id_and_nonfinite_candidates_excluded():
    positions = rank_topk(np.array([2., 2., -np.inf, np.nan]), np.array([9, 3, 2, 1]), 10)
    assert list(positions) == [1, 0]


def test_weight_zero_exactly_preserves_base_ranking():
    scores = np.array([4., 2., 4., -np.inf])
    ids = np.array([9, 8, 3, 1])
    chosen, _ = rerank(scores, ids, np.array([1, 20, 100, 8]), 3, 0., 3)
    assert list(ids[chosen]) == [3, 9, 8]


def test_novelty_only_can_change_order_but_not_escape_pool():
    scores = np.array([3., 2., 1.])
    ids = np.array([1, 2, 3])
    chosen, _ = rerank(scores, ids, np.array([100, 1, 0]), 2, 1., 2)
    assert list(ids[chosen]) == [2, 1]
    assert 3 not in ids[chosen]


def test_novelty_decreases_with_popularity():
    values = novelty_scores(np.array([0, 1, 100]))
    assert values[0] > values[1] > values[2]


def test_all_filtered_candidates_return_empty():
    chosen, mixed = rerank(np.full(3, -np.inf), np.arange(3), np.ones(3), 2)
    assert len(chosen) == len(mixed) == 0


@pytest.mark.parametrize("weight,pool", [(-.1, 10), (1.1, 10), (.1, 1)])
def test_invalid_rerank_parameters_fail(weight, pool):
    with pytest.raises(ValueError):
        rerank(np.ones(3), np.arange(3), np.ones(3), 2, weight, pool)
