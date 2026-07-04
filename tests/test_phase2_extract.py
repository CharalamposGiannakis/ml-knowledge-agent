"""Pure-function tests for scripts/phase2_extract.py (ADR-015 audit, item A6)."""
import pytest

from phase2_extract import _canon_local, _normalise_result, _parse_cell, emit_ttl

# ── _parse_cell ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw_cell, expected",
    [
        ("78.93 ± 0.73", (78.93, 0.73)),
        ("78.93", (78.93, None)),
        ("1,234.56 ± 0.1", (1234.56, 0.1)),
        ("-78.93 ± 0.73", (-78.93, 0.73)),          # negatives
        ("−78.93 ± 0.73", (-78.93, 0.73)),  # unicode minus (U+2212)
        ("78.93+/-0.73", (78.93, 0.73)),             # ascii +/- variant
        ("78.93% ± 0.73%", (78.93, 0.73)),       # percent
        ("2.5e-3 ± 1e-4", (0.0025, 0.0001)),     # scientific notation
    ],
)
def test_parse_cell_valid(raw_cell, expected):
    assert _parse_cell(raw_cell) == expected


@pytest.mark.parametrize(
    "raw_cell",
    [
        "78.93†",       # footnote marker
        "**78.93**",         # bold/markdown contamination
        "78.93 (n=5)",       # trailing annotation
        "",
        "n/a",
    ],
)
def test_parse_cell_unparseable_returns_none(raw_cell):
    assert _parse_cell(raw_cell) == (None, None)


# ── _canon_local ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "uri, expected",
    [
        (":XGBoost", "xgboost"),
        (":ds_gesture", "ds_gesture"),
        (":Cross-Entropy Loss", "cross_entropy_loss"),
        (":1D-CNN", "1d_cnn"),
    ],
)
def test_canon_local(uri, expected):
    assert _canon_local(uri) == expected


# ── _normalise_result ────────────────────────────────────────────────────────

VOCAB = {
    "xgboost": {"uri": ":XGBoost", "label": "XGBoost", "type": "Method"},
    "gesture phase": {"uri": ":ds_gesture", "label": "Gesture Phase", "type": "Dataset"},
    "cross-entropy loss": {"uri": ":CrossEntropyLoss", "label": "Cross-entropy loss", "type": "Metric"},
}


def _base_result(**overrides) -> dict:
    r = {
        "method_raw": "XGBoost",
        "method_canonical": None,
        "dataset_raw": "Gesture Phase",
        "dataset_canonical": None,
        "metric_raw": "cross-entropy loss",
        "metric_canonical": None,
        "value": 80.64,
        "std_error": 0.80,
        "raw_cell": "80.64 ± 0.80",
        "conditions": [],
        "conditions_complete": False,
        "flags": [],
    }
    r.update(overrides)
    return r


def _reasons(result: dict) -> set:
    return {f["reason"] for f in result["flags"]}


def test_normalise_clean_record_resolves_all_canonicals_no_flags():
    result = _normalise_result(_base_result(), VOCAB)
    assert result["method_canonical"] == ":XGBoost"
    assert result["dataset_canonical"] == ":ds_gesture"
    assert result["metric_canonical"] == ":CrossEntropyLoss"
    assert result["flags"] == []


def test_normalise_missing_required_field():
    result = _normalise_result(_base_result(method_raw=None), VOCAB)
    assert "missing_required" in _reasons(result)


def test_normalise_no_alias_match_for_unknown_dataset():
    result = _normalise_result(_base_result(dataset_raw="Unknown Dataset"), VOCAB)
    assert "no_alias_match" in _reasons(result)


def test_normalise_metric_not_in_vocab():
    result = _normalise_result(_base_result(metric_raw="Unknown Metric"), VOCAB)
    assert "metric_not_in_vocab" in _reasons(result)


def test_normalise_type_mismatch():
    # "Gesture Phase" resolves via vocab, but as a Dataset, not a Method.
    result = _normalise_result(_base_result(method_raw="Gesture Phase"), VOCAB)
    assert "type_mismatch" in _reasons(result)


def test_normalise_value_parse_mismatch():
    result = _normalise_result(_base_result(value=99.0), VOCAB)
    assert "value_parse_mismatch" in _reasons(result)


def test_normalise_std_error_parse_mismatch():
    result = _normalise_result(_base_result(std_error=99.0), VOCAB)
    assert "value_parse_mismatch" in _reasons(result)


def test_normalise_value_unverifiable_when_raw_cell_unparseable():
    result = _normalise_result(_base_result(raw_cell="80.64† (see note)"), VOCAB)
    assert "value_unverifiable" in _reasons(result)


# ── emit_ttl ─────────────────────────────────────────────────────────────────


def _clean_doc(*results) -> dict:
    return {
        "paper_id": "shwartzziv2022",
        "extracted_by": "claude-opus-4-8@prompt-1.0",
        "source": {"locator": "Table 2", "page": 6, "caption": "..."},
        "table_flags": [],
        "results": list(results),
    }


def _clean_result(**overrides) -> dict:
    r = _base_result(**overrides)
    r["method_canonical"] = overrides.get("method_canonical", ":XGBoost")
    r["dataset_canonical"] = overrides.get("dataset_canonical", ":ds_gesture")
    r["metric_canonical"] = overrides.get("metric_canonical", ":CrossEntropyLoss")
    r["flags"] = []
    return r


def test_emit_ttl_iri_is_deterministic():
    doc1 = _clean_doc(_clean_result())
    doc2 = _clean_doc(_clean_result())
    ttl1 = emit_ttl(doc1)
    ttl2 = emit_ttl(doc2)
    assert ttl1 == ttl2
    assert ":r_shwartzziv2022__xgboost__ds_gesture__crossentropyloss" in ttl1


def test_emit_ttl_duplicate_key_collides_to_same_iri():
    # Same (method, dataset, metric) canonical key twice -> same IRI both times.
    # emit_ttl does not dedupe (that's Layer 2 invariant C's job) but the IRIs
    # must be identical so the duplicate is even detectable downstream.
    doc = _clean_doc(_clean_result(value=80.64), _clean_result(value=80.70))
    ttl = emit_ttl(doc)
    assert ttl.count(":r_shwartzziv2022__xgboost__ds_gesture__crossentropyloss") == 2


def test_emit_ttl_skips_flagged_records():
    flagged = _base_result()
    flagged["flags"] = [{"field": "value", "reason": "value_unverifiable",
                          "question": "?", "options": [], "requires_human_answer": True}]
    doc = _clean_doc(flagged)
    ttl = emit_ttl(doc)
    assert "No clean records" in ttl
