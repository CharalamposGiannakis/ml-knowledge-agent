"""SPARQL invariant tests (ADR-015 audit, item A3/A4).

Runs the exact query strings from scripts/healthcheck.py's CHECKS list against
an in-memory rdflib graph (ontology + fixture), so this doesn't require a live
Fuseki. This is what replaced the owlrl-based Layer 3, which the audit found
did not actually catch these violations.
"""
from rdflib import Graph

from conftest import REPO_ROOT, FIXTURES_DIR
from healthcheck import CHECKS

ONTOLOGY_FILE = REPO_ROOT / "ontology" / "mlkg.ttl"


def _check(check_id: str) -> dict:
    return next(c for c in CHECKS if c["id"] == check_id)


def _graph_with(fixture_name: str) -> Graph:
    g = Graph()
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    g.parse(str(FIXTURES_DIR / fixture_name), format="turtle")
    return g


def test_multivalue_invariant_catches_two_hasvalue_literals():
    g = _graph_with("bad_multivalue.ttl")
    rows = list(g.query(_check("H")["query"]))
    assert len(rows) >= 1, "check H should flag a BenchmarkResult with two different :hasValue literals"


def test_multivalue_invariant_clean_on_full_extraction_data():
    g = Graph()
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    g.parse(str(REPO_ROOT / "data" / "shwartzziv2022_full.ttl"), format="turtle")
    rows = list(g.query(_check("H")["query"]))
    assert len(rows) == 0, "data/shwartzziv2022_full.ttl should have no multi-valued :hasValue"


def test_cross_typing_invariants_clean_on_ontology_alone():
    g = Graph()
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    for check_id in ("E", "F", "G"):
        rows = list(g.query(_check(check_id)["query"]))
        assert rows == [], f"check {check_id} should be clean on the ontology's own vocabulary"
