"""Scorer key-matching tests (ADR-015 audit, item A6)."""
from eval_extraction import match_to_gold

GOLD = {
    (":XGBoost", ":ds_gesture", ":CrossEntropyLoss"): {
        "value": 80.64, "std_error": 0.80, "locator": "Table 2", "page": 6,
    },
    (":NODE", ":ds_higgs", ":CrossEntropyLoss"): {
        "value": 21.19, "std_error": 0.69, "locator": "Table 2", "page": 6,
    },
}


def _result(method, dataset, metric) -> dict:
    return {
        "method_canonical": method,
        "dataset_canonical": dataset,
        "metric_canonical": metric,
        "value": 80.64,
    }


def test_match_to_gold_exact_key_match():
    results = [_result(":XGBoost", ":ds_gesture", ":CrossEntropyLoss")]
    matched, unmatched = match_to_gold(results, GOLD)
    assert len(matched) == 1
    assert unmatched == []
    r, g = matched[0]
    assert g["value"] == 80.64


def test_match_to_gold_no_match_for_key_outside_gold():
    results = [_result(":TabNet", ":ds_gesture", ":CrossEntropyLoss")]
    matched, unmatched = match_to_gold(results, GOLD)
    assert matched == []
    assert len(unmatched) == 1


def test_match_to_gold_does_not_confuse_partial_key_overlap():
    # Same method+metric as a gold entry but a different dataset -- must not match.
    results = [_result(":XGBoost", ":ds_rossmann", ":CrossEntropyLoss")]
    matched, unmatched = match_to_gold(results, GOLD)
    assert matched == []
    assert len(unmatched) == 1


def test_match_to_gold_multiple_records_partition_correctly():
    results = [
        _result(":XGBoost", ":ds_gesture", ":CrossEntropyLoss"),
        _result(":NODE", ":ds_higgs", ":CrossEntropyLoss"),
        _result(":Unknown", ":ds_unknown", ":CrossEntropyLoss"),
    ]
    matched, unmatched = match_to_gold(results, GOLD)
    assert len(matched) == 2
    assert len(unmatched) == 1
