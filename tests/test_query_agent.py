"""Query-agent tests (ADR-018) — all offline, against an in-memory rdflib
graph, so they exercise exactly the SPARQL and shapers used in production
(FusekiBackend and RdflibBackend share the row shape).

Covers: metric direction both ways, empty result, alias resolution, unknown
term, SPARQL-injection/slot rejection, narration guard, seen/unseen ranks,
and the full loop with a fake planner (no LLM anywhere in these tests).
"""
import pytest
from rdflib import Graph

from conftest import FIXTURES_DIR

from agent.catalog import Catalog
from agent.loop import answer_question
from agent.narrator import Narrator, guard, template_answer
from agent.operations import OPERATIONS, SlotError
from agent.planner import Plan
from agent.sparql import RdflibBackend

NS = "http://mlkg.local/ontology#"


def uri(local: str) -> str:
    return NS + local


@pytest.fixture(scope="module")
def backend():
    g = Graph()
    g.parse(FIXTURES_DIR / "agent_toy_graph.ttl", format="turtle")
    return RdflibBackend(g)


@pytest.fixture(scope="module")
def catalog(backend):
    return Catalog.fetch(backend)


class SpyBackend:
    """Records queries; delegates to a real backend (or refuses if sealed)."""

    def __init__(self, inner=None):
        self.inner = inner
        self.queries = []

    def select(self, sparql):
        self.queries.append(sparql)
        if self.inner is None:
            raise AssertionError("backend must not be queried in this test")
        return self.inner.select(sparql)


class FakePlanner:
    def __init__(self, plan: Plan):
        self._plan = plan

    def plan(self, question, catalog):
        return self._plan


def run(question, plan, backend, catalog):
    return answer_question(
        question,
        backend=backend,
        catalog=catalog,
        planner=FakePlanner(plan),
        narrator=Narrator(use_llm=False),
    )


# ── operation SPARQL + shapers ────────────────────────────────────────────────

def test_compare_higher_is_better(backend):
    op = OPERATIONS["compare_pair"]
    slots = {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
             "dataset": uri("ds_alpha"), "metric": uri("Accuracy")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    [c] = shaped["comparisons"]
    assert c["direction"] == "higher is better"
    assert c["winner"] == uri("XGBoost")
    assert c["margin"] == pytest.approx(0.1)


def test_compare_lower_is_better(backend):
    op = OPERATIONS["compare_pair"]
    slots = {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
             "dataset": uri("ds_alpha"), "metric": uri("LogLoss")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    [c] = shaped["comparisons"]
    assert c["direction"] == "lower is better"
    assert c["winner"] == uri("TabNet")


def test_compare_without_metric_covers_all_shared_metrics(backend):
    op = OPERATIONS["compare_pair"]
    slots = {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
             "dataset": uri("ds_alpha")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    winners = {c["metric_label"]: c["winner"] for c in shaped["comparisons"]}
    assert winners == {"Accuracy": uri("XGBoost"), "Log loss": uri("TabNet")}


def test_best_on_dataset_ranks_by_direction(backend):
    op = OPERATIONS["best_on_dataset"]
    slots = {"dataset": uri("ds_alpha"), "metric": uri("Accuracy")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    [ranking] = shaped["rankings"]
    assert ranking["best"]["method"] == uri("XGBoost")
    assert [r["method_label"] for r in ranking["ranking"]] == \
        ["XGBoost", "NODE", "TabNet"]
    assert [r["rank"] for r in ranking["ranking"]] == [1, 2, 3]


def test_lookup_carries_value_and_citation(backend):
    op = OPERATIONS["lookup_result"]
    slots = {"method": uri("XGBoost"), "dataset": uri("ds_alpha"),
             "metric": uri("Accuracy")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    [r] = shaped["results"]
    assert r["value"] == 0.9
    assert r["std_error"] == 0.01
    assert r["citation"] == {"paper": "Toy Paper", "year": 2026,
                             "locator": "Table 9", "page": 3}


def test_seen_unseen_mean_ranks(backend):
    op = OPERATIONS["seen_unseen"]
    slots = {"method": uri("TabNet")}
    shaped = op.shape(backend.select(op.build_sparql(slots)), slots)
    # seen: Alpha/Accuracy rank 3 of 3, Alpha/LogLoss rank 1 of 2 -> mean 2.0
    # unseen: Beta/Accuracy rank 1 of 3 -> mean 1.0
    assert shaped["seen"] == {"n_datasets": 2, "mean_rank": 2.0, "wins": 1}
    assert shaped["unseen"] == {"n_datasets": 1, "mean_rank": 1.0, "wins": 1}


# ── catalog: alias resolution / unknown terms ─────────────────────────────────

def test_alias_resolution(catalog):
    assert [e.uri for e in catalog.find("XGB")] == [uri("XGBoost")]
    assert [e.uri for e in catalog.find("alpha")] == [uri("ds_alpha")]
    assert [e.uri for e in catalog.find("Acc")] == [uri("Accuracy")]


def test_unknown_term_matches_nothing(catalog):
    assert catalog.find("BERT") == []


# ── trust boundary: nothing model-authored reaches the query ──────────────────

def test_injection_slot_raises_before_query_is_built():
    op = OPERATIONS["compare_pair"]
    slots = {"method_a": uri("XGBoost") + "> } . ?s ?p ?o . { <x",
             "method_b": uri("TabNet"), "dataset": uri("ds_alpha")}
    with pytest.raises(SlotError):
        op.build_sparql(slots)


def test_loop_rejects_uri_outside_catalog(catalog):
    sealed = SpyBackend(inner=None)  # any select() call fails the test
    plan = Plan(operation="lookup_result",
                slots={"method": uri("Bogus"), "dataset": uri("ds_alpha")})
    answer = answer_question("q", backend=sealed, catalog=catalog,
                             planner=FakePlanner(plan),
                             narrator=Narrator(use_llm=False))
    assert answer.status == "error"
    assert "not an entity in the graph catalog" in answer.text
    assert sealed.queries == []


def test_loop_rejects_wrong_entity_type(catalog):
    sealed = SpyBackend(inner=None)
    plan = Plan(operation="lookup_result",
                slots={"method": uri("ds_alpha"), "dataset": uri("ds_beta")})
    answer = answer_question("q", backend=sealed, catalog=catalog,
                             planner=FakePlanner(plan),
                             narrator=Narrator(use_llm=False))
    assert answer.status == "error"
    assert sealed.queries == []


# ── honesty statuses through the loop ─────────────────────────────────────────

def test_empty_result_is_not_in_graph(backend, catalog):
    plan = Plan(operation="best_on_dataset", slots={"dataset": uri("ds_empty")})
    answer = run("best on empty?", plan, backend, catalog)
    assert answer.status == "not_in_graph"
    assert "doesn't contain" in answer.text


def test_one_sided_comparison_is_not_an_answer(backend, catalog):
    # NODE has no Log loss row on Alpha: no shared (dataset, metric).
    plan = Plan(operation="compare_pair",
                slots={"method_a": uri("NODE"), "method_b": uri("TabNet"),
                       "dataset": uri("ds_alpha"), "metric": uri("LogLoss")})
    answer = run("did NODE beat TabNet on Alpha log loss?", plan, backend, catalog)
    assert answer.status == "not_in_graph"
    assert "share no (dataset, metric)" in answer.text
    assert "only TabNet has a Log loss result" in answer.text  # honest partial


def test_unresolved_term_is_reported(backend, catalog):
    plan = Plan(operation="lookup_result", unresolved_terms=["BERT"])
    answer = run("how does BERT do?", plan, backend, catalog)
    assert answer.status == "not_in_graph"
    assert "'BERT'" in answer.text


def test_ambiguity_asks_to_disambiguate(backend, catalog):
    plan = Plan(operation="lookup_result",
                ambiguities=[{"term": "the model",
                              "candidates": [uri("XGBoost"), uri("TabNet")]}])
    answer = run("how did the model do?", plan, backend, catalog)
    assert answer.status == "ambiguous"
    assert "XGBoost" in answer.text and "TabNet" in answer.text


def test_unsupported_is_honest(backend, catalog):
    plan = Plan(operation="unsupported", note="causal question")
    answer = run("why do trees win?", plan, backend, catalog)
    assert answer.status == "unsupported"
    assert "can't express" in answer.text


# ── narration guard ───────────────────────────────────────────────────────────

def _shaped_compare(backend):
    op = OPERATIONS["compare_pair"]
    slots = {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
             "dataset": uri("ds_alpha"), "metric": uri("Accuracy")}
    return op.shape(backend.select(op.build_sparql(slots)), slots)


def test_guard_accepts_template(backend):
    shaped = _shaped_compare(backend)
    ok, reason = guard(template_answer(shaped), shaped)
    assert ok, reason


def test_guard_rejects_foreign_number(backend):
    shaped = _shaped_compare(backend)
    text = "XGBoost wins with 0.95 accuracy (Table 9, p.3)."
    ok, reason = guard(text, shaped)
    assert not ok and "0.95" in reason


def test_guard_requires_citation(backend):
    shaped = _shaped_compare(backend)
    text = "XGBoost got 0.9 and TabNet 0.8, so XGBoost wins."
    ok, reason = guard(text, shaped)
    assert not ok and "citation" in reason


# ── full loop, flagship shape ─────────────────────────────────────────────────

def test_full_loop_compare_template(backend, catalog):
    plan = Plan(operation="compare_pair",
                slots={"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
                       "dataset": uri("ds_alpha"), "metric": uri("Accuracy")})
    answer = run("Did XGBoost beat TabNet on Alpha?", plan, backend, catalog)
    assert answer.status == "answered"
    assert answer.narration_source == "template"
    assert "XGBoost wins" in answer.text
    assert "Table 9, p.3" in answer.text
    assert answer.citations == ["Table 9, p.3"]
    ok, reason = guard(answer.text, answer.shaped)
    assert ok, reason
