"""SHACL pre-load gate tests (ADR-015 audit, item A3).

Mirrors the merge-and-validate logic in scripts/validate_shapes.py directly
(rather than shelling out) so failures point at pyshacl's report text.
"""
import pyshacl
from rdflib import Graph

from conftest import REPO_ROOT, FIXTURES_DIR

SHAPES_FILE = REPO_ROOT / "ontology" / "shapes.ttl"
ONTOLOGY_FILE = REPO_ROOT / "ontology" / "mlkg.ttl"


def _gate(data_path) -> tuple:
    shapes_graph = Graph().parse(str(SHAPES_FILE), format="turtle")
    data_graph = Graph().parse(str(ONTOLOGY_FILE), format="turtle")
    data_graph += Graph().parse(str(data_path), format="turtle")

    conforms, _, results_text = pyshacl.validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
        meta_shacl=False,
        advanced=False,
        js=False,
        debug=False,
    )
    return conforms, results_text


def test_gate_rejects_dangling_dataset():
    conforms, report = _gate(FIXTURES_DIR / "bad_dangling_dataset.ttl")
    assert not conforms, f"gate should reject a dangling :onDataset URI:\n{report}"


def test_gate_rejects_disjoint_type():
    conforms, report = _gate(FIXTURES_DIR / "bad_disjoint_type.ttl")
    assert not conforms, (
        f"gate should reject :onDataset pointing at a :Method (disjoint from "
        f":Dataset) — this is the vacuous-inference regression:\n{report}"
    )


def test_gate_passes_full_extraction_data():
    conforms, report = _gate(REPO_ROOT / "data" / "shwartzziv2022_full.ttl")
    assert conforms, f"data/shwartzziv2022_full.ttl should still conform:\n{report}"
