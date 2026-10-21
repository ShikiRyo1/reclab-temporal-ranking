import json

import pytest

from reclab.train import run


@pytest.mark.parametrize("k,threshold", [(5, 4), (20, 4), (10, 3), (10, 5)])
def test_unsupported_protocol_rejected_before_data_or_output(tmp_path, k, threshold):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"k": k, "positive_threshold": threshold}))
    output = tmp_path / "reports"
    with pytest.raises(ValueError, match="k=10 and positive_threshold=4"):
        run(tmp_path / "missing-data", config, output, tmp_path / "model.joblib")
    assert not output.exists()
