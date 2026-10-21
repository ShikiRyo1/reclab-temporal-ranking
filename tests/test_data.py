import numpy as np
import pandas as pd
import pytest

from reclab.data import eligible_targets, history_map, temporal_split


def test_equal_timestamps_never_cross_split():
    frame = pd.DataFrame({"timestamp": [1, 1, 2, 2, 3, 3, 4, 4]})
    train, valid, test, info = temporal_split(frame, 0.5, 0.25)
    assert train.timestamp.max() < valid.timestamp.min() < test.timestamp.min()
    assert len(train) + len(valid) + len(test) == len(frame)
    assert info["train_cutoff"] == 2


def test_tied_empty_partition_fails_instead_of_leaking():
    with pytest.raises(ValueError, match="empty partition"):
        temporal_split(pd.DataFrame({"timestamp": [1] * 10}))


def test_low_ratings_are_seen_and_unavailable_positives_are_counted():
    past = pd.DataFrame({"user_id": [1, 1], "item_id": [10, 20], "rating": [1, 5]})
    future = pd.DataFrame({"user_id": [1, 1, 1, 2], "item_id": [10, 30, 99, 20],
                           "rating": [5, 4, 5, 2]})
    truth, counts = eligible_targets(future, np.array([10, 20, 30]), history_map(past))
    assert truth == {1: {30}}
    assert counts["already_seen_positive_rows"] == 1
    assert counts["out_of_training_catalog_positive_rows"] == 1
    assert counts["eligible_positive_rows"] == 1


@pytest.mark.parametrize("train,validation", [(0, .1), (.9, .2), (.5, 0)])
def test_invalid_fractions_fail(train, validation):
    with pytest.raises(ValueError):
        temporal_split(pd.DataFrame({"timestamp": range(10)}), train, validation)
