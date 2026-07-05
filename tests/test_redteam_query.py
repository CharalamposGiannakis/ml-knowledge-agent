"""Red-team regression suite for the query layer (see docs/redteam.md).

Adversarial probes of the five seams where language crosses into the formal
query: RESOLUTION, SELECTION, SLOT-FILLING, NARRATION, HONESTY — plus the
eval MEASUREMENT itself.

Two kinds of test live here:

* Plain tests pin a defense that currently HOLDS, so a future change that
  weakens it fails loudly (e.g. the slot-injection gate).
* ``xfail(strict=True)`` tests encode the SECURE behavior for a hole that is
  currently OPEN. They fail today (hence xfail), and the moment the guard is
  fixed they XPASS — which, under ``strict``, fails the suite and forces
  whoever fixed it to drop the marker. That is the tripwire that stops a
  finding from silently regressing back in.

Every test is offline: an in-memory rdflib graph, the real operations/guard,
and a fake planner. No LLM, no network.
"""
import inspect
import sys
from pathlib import Path

import pytest
from rdflib import Graph

from conftest import FIXTURES_DIR

from agent.catalog import Catalog
from agent.loop import answer_question
from agent.narrator import Narrator, guard
from agent.operations import OPERATIONS, SlotError
from agent.planner import Plan
from agent.sparql import RdflibBackend

NS = "http://mlkg.local/ontology#"


def uri(local: str) -> str:
    return NS + local


class FakePlanner:
    def __init__(self, plan: Plan):
        self._plan = plan

    def plan(self, question, catalog):
        return self._plan


def run(plan, backend, catalog, question="q"):
    return answer_question(question, backend=backend, catalog=catalog,
                           planner=FakePlanner(plan),
                           narrator=Narrator(use_llm=False))


def graph_from(ttl: str) -> RdflibBackend:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return RdflibBackend(g)


@pytest.fixture(scope="module")
def toy():
    g = Graph()
    g.parse(FIXTURES_DIR / "agent_toy_graph.ttl", format="turtle")
    be = RdflibBackend(g)
    return be, Catalog.fetch(be)


def _shape(backend, op_name, slots):
    op = OPERATIONS[op_name]
    return op.shape(backend.select(op.build_sparql(slots)), slots)


# ── SEAM 3: SLOT-FILLING — defense that HOLDS (pin it) ────────────────────────

@pytest.mark.parametrize("payload", [
    uri("XGBoost") + "> } . ?s ?p ?o . { <x",         # break out of <...>
    uri("XGBoost") + " UNION { ?x ?y ?z }",            # graft a UNION
    uri("XGBoost") + "\n  ?s ?p ?o .",                 # newline injection
    "http://evil.example/x",                            # off-namespace URI
    "javascript:alert(1)",                              # not a URI at all
    uri("XGBoost") + "#frag",                          # extra fragment char
])
def test_seam3_slot_injection_never_builds(payload):
    """No crafted slot value reaches the SPARQL string: the _SAFE_URI gate
    rejects anything but `#<alnum/underscore>` in the ontology namespace."""
    op = OPERATIONS["lookup_result"]
    with pytest.raises(SlotError):
        op.build_sparql({"method": payload, "dataset": uri("ds_alpha")})


def test_seam3_metric_slot_injection_never_builds():
    """The optional metric slot is gated too (regression: only the method slot
    was covered before)."""
    op = OPERATIONS["compare_pair"]
    with pytest.raises(SlotError):
        op.build_sparql({"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
                         "dataset": uri("ds_alpha"),
                         "metric": uri("Accuracy") + "> } ?s ?p ?o {<x"})


def test_seam3_out_of_catalog_uri_never_queries(toy):
    """A well-formed-but-unknown URI is refused before any SELECT runs."""
    be, cat = toy

    class Sealed:
        queries = []

        def select(self, q):
            raise AssertionError("must not query")

    ans = answer_question("q", backend=Sealed(), catalog=cat,
                          planner=FakePlanner(Plan(
                              operation="lookup_result",
                              slots={"method": uri("Nonexistent"),
                                     "dataset": uri("ds_alpha")})),
                          narrator=Narrator(use_llm=False))
    assert ans.status == "error"
    assert "not an entity in the graph catalog" in ans.text


# ── SEAM 4: NARRATION — the guard is truth-blind (OPEN holes) ─────────────────
#
# The guard accepts any prose in which (a) every number already appears
# somewhere in the payload and (b) one payload citation string is present. It
# never binds a number to a claim, a citation to a claim, or the optimization
# direction to the word "beat". So true tokens can be permuted into a false
# sentence and still pass. Each test below asserts the SECURE outcome (guard
# rejects) and is therefore an xfail tripwire until the guard checks meaning.

def _compare_loss(toy):
    # lower-is-better: TabNet 0.2 BEATS XGBoost 0.3
    be, _ = toy
    return _shape(be, "compare_pair",
                  {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
                   "dataset": uri("ds_alpha"), "metric": uri("LogLoss")})


def _compare_acc(toy):
    # higher-is-better, XGBoost 0.9 (± 0.01) beats TabNet 0.8
    be, _ = toy
    return _shape(be, "compare_pair",
                  {"method_a": uri("XGBoost"), "method_b": uri("TabNet"),
                   "dataset": uri("ds_alpha"), "metric": uri("Accuracy")})


@pytest.mark.xfail(strict=True, reason="redteam F1: guard is truth-blind — "
                   "wrong winner with real numbers passes")
def test_seam4_wrong_winner_rejected(toy):
    shaped = _compare_loss(toy)
    # FALSE: TabNet (0.2) actually won; values are also swapped between methods.
    text = ("XGBoost beat TabNet on Alpha Phase, 0.2 to 0.3 "
            "(Toy Paper, Table 9, p.3).")
    ok, _ = guard(text, shaped)
    assert not ok, "guard must reject a narration that names the wrong winner"


@pytest.mark.xfail(strict=True, reason="redteam F1: guard ignores optimization "
                   "direction — 'higher' claim on a lower-is-better metric passes")
def test_seam4_inverted_direction_rejected(toy):
    shaped = _compare_loss(toy)
    # FALSE: log loss is lower-is-better; 0.3 is not "higher/better".
    text = ("XGBoost posted the higher score, 0.3 versus 0.2, so it wins "
            "(Table 9, p.3).")
    ok, _ = guard(text, shaped)
    assert not ok, "guard must respect optimizationDirection"


@pytest.mark.xfail(strict=True, reason="redteam F1: guard lets the std error "
                   "be narrated as the value")
def test_seam4_sem_as_value_rejected(toy):
    shaped = _compare_acc(toy)  # XGBoost value 0.9, std_error 0.01
    # FALSE: 0.01 is the standard error, not the score.
    text = "XGBoost scored 0.01 on Alpha Phase (Table 9, p.3)."
    ok, _ = guard(text, shaped)
    assert not ok, "guard must not accept a SEM presented as the value"


@pytest.mark.xfail(strict=True, reason="redteam F1: metadata numbers (locator "
                   "digits, year, page) pollute the value whitelist")
def test_seam4_metadata_number_as_data_rejected(toy):
    shaped = _compare_acc(toy)
    # FALSE: "9" is only in the payload because the locator is 'Table 9';
    # it is not a benchmark value, yet the guard admits it as one.
    text = "XGBoost led TabNet by 9 accuracy points (Table 9, p.3)."
    ok, _ = guard(text, shaped)
    assert not ok, "digits from citations/years must not be usable as values"


# ── SEAM 5 / SELECTION: cross-paper conflation (OPEN hole) ────────────────────

CROSS_PAPER = """@prefix : <http://mlkg.local/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
:Acc a :Metric ; rdfs:label "Accuracy" ; :optimizationDirection :HigherIsBetter .
:A a :Method ; rdfs:label "A" .
:B a :Method ; rdfs:label "B" .
:d a :Dataset ; rdfs:label "D" .
:p1 a :Paper ; :title "Paper One" ; :year 2020 .
:p2 a :Paper ; :title "Paper Two" ; :year 2023 .
:s1 a :SourceLocation ; :fromPaper :p1 ; :locator "T1" ; :page 1 .
:s2 a :SourceLocation ; :fromPaper :p2 ; :locator "T2" ; :page 2 .
:ra1 a :BenchmarkResult ; :reportsMethod :A ; :onDataset :d ; :usesMetric :Acc ; :hasValue 0.70 ; :hasSource :s1 .
:ra2 a :BenchmarkResult ; :reportsMethod :A ; :onDataset :d ; :usesMetric :Acc ; :hasValue 0.95 ; :hasSource :s2 .
:rb1 a :BenchmarkResult ; :reportsMethod :B ; :onDataset :d ; :usesMetric :Acc ; :hasValue 0.80 ; :hasSource :s1 .
"""


@pytest.mark.xfail(strict=True, reason="redteam F2: compare silently uses a[0] "
                   "when a (method,dataset,metric) cell has multiple results")
def test_selection_cross_paper_conflation_flagged():
    be = graph_from(CROSS_PAPER)
    slots = {"method_a": uri("A"), "method_b": uri("B"),
             "dataset": uri("d"), "metric": uri("Acc")}
    rows = be.select(OPERATIONS["compare_pair"].build_sparql(slots))
    a_values = sorted(float(r["value"]) for r in rows if r["method"] == uri("A"))
    assert a_values == [0.70, 0.95]  # two papers report A on this cell

    shaped = OPERATIONS["compare_pair"].shape(rows, slots)
    c = shaped["comparisons"][0]
    used = c["a"]["value"]
    dropped = [v for v in a_values if v != used]
    # SECURE behavior: the conflicting result must not vanish without a trace.
    # It is currently dropped silently and the winner is decided from whichever
    # row the store returned first (unstable across runs).
    signalled = (
        shaped["one_sided"]
        or "multiple" in shaped
        or any(any(k in c for k in ("conflict", "sources", "all_values"))
               for c in shaped["comparisons"])
    )
    assert not dropped or signalled, (
        f"A also scored {dropped} in another paper; the comparison hid it and "
        f"declared winner={c['winner_label']!r} from an arbitrary row")


# ── SEAM 4/5: seen_unseen mislabels the queried method (OPEN hole) ────────────

SEEN_ONLY = """@prefix : <http://mlkg.local/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
:Acc a :Metric ; rdfs:label "Accuracy" ; :optimizationDirection :HigherIsBetter .
:M a :Method ; rdfs:label "M" .
:Other a :Method ; rdfs:label "Other" .
:d1 a :Dataset ; rdfs:label "D1" .
:p a :Paper ; :title "P" ; :year 2020 .
:s a :SourceLocation ; :fromPaper :p ; :locator "Tab 1" ; :page 1 .
:r1 a :BenchmarkResult ; :reportsMethod :M ; :onDataset :d1 ; :usesMetric :Acc ; :hasValue 0.9 ; :hasSource :s ; :datasetSeenByModel "seen" .
:r2 a :BenchmarkResult ; :reportsMethod :Other ; :onDataset :d1 ; :usesMetric :Acc ; :hasValue 0.5 ; :hasSource :s .
"""


@pytest.mark.xfail(strict=True, reason="redteam F3: seen_unseen labels the "
                   "whole answer with rows[0]'s method, not the queried one")
def test_seen_unseen_labels_queried_method():
    be = graph_from(SEEN_ONLY)
    shaped = _shape(be, "seen_unseen", {"method": uri("M")})
    # The question is about M; the label must be M, not whichever method the
    # store sorted first (here 'Other', which has the lower value).
    assert shaped["method_label"] == "M"


@pytest.mark.xfail(strict=True, reason="redteam F4: one-sided seen/unseen is "
                   "presented as a two-sided comparison")
def test_seen_unseen_one_sided_not_answered_as_two_sided():
    be = graph_from(SEEN_ONLY)  # M has a seen dataset but no unseen one
    ans = run(Plan(operation="seen_unseen", slots={"method": uri("M")}),
              be, Catalog.fetch(be))
    unseen = ans.shaped["unseen"]
    # SECURE: a bucket with no data must not read as a completed comparison.
    two_sided_claim = (ans.status == "answered"
                       and unseen["n_datasets"] == 0
                       and unseen["mean_rank"] is None)
    assert not two_sided_claim, (
        "comparing 'seen vs unseen' with zero unseen datasets is one-sided")


# ── SEAM 1: RESOLUTION has no deterministic backstop (OPEN hole) ──────────────

@pytest.mark.xfail(strict=True, reason="redteam F6: the loop trusts the "
                   "planner's slot URIs; a same-type mis-resolution executes")
def test_resolution_same_type_misresolution_is_caught(toy):
    be, cat = toy
    # The user asked about XGBoost; the planner (mis)fills the TabNet URI.
    # Both are Methods, so the type/membership check passes and the wrong
    # method's numbers come back cited and confident. There is no deterministic
    # cross-check that the chosen URI matches the question's surface term.
    ans = run(Plan(operation="lookup_result",
                   slots={"method": uri("TabNet"), "dataset": uri("ds_alpha"),
                          "metric": uri("Accuracy")}),
              be, cat, question="What accuracy did XGBoost get on Alpha?")
    # SECURE behavior would refuse or flag; today it answers with TabNet's value.
    assert ans.status != "answered"


# ── MEASUREMENT: the eval cannot see any of the above (OPEN hole) ─────────────

def test_eval_never_scores_llm_narration():
    """The eval runs with template narration, so the one component that can
    fabricate — the LLM narrator — is never exercised by the score. Pinned so
    that turning it on (or off, deliberately) is a conscious change."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
    import run_eval
    src = inspect.getsource(run_eval.main)
    assert "use_llm=False" in src, (
        "eval scores structured payloads only; LLM prose is unmeasured "
        "(redteam F5)")


@pytest.mark.xfail(strict=True, reason="redteam F5: eval value check is "
                   "union-based and cannot localize a value to a claim")
def test_eval_value_check_localizes_to_claim():
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
    import run_eval

    be = graph_from(CROSS_PAPER)
    ans = run(Plan(operation="compare_pair",
                   slots={"method_a": uri("A"), "method_b": uri("B"),
                          "dataset": uri("d"), "metric": uri("Acc")}),
              be, Catalog.fetch(be))
    # 0.80 is method B's value. A human asking "what did A score?" and being
    # shown B's number would call that wrong; the union-based value check does
    # not, because 0.80 appears *somewhere* in the payload.
    fails = run_eval.check_retrieval(ans, {"status": "answered", "value": 0.80})
    assert fails, "eval must tie an expected value to the method it belongs to"
