"""The agent loop: resolve -> select -> execute -> narrate -> guard (ADR-018).

Deterministic code owns every step that can be wrong silently:
- slot URIs must be catalog members of the slot's entity type (resolve),
- only registry operations run, with code-built SPARQL (select/execute),
- winners come from :optimizationDirection inside the shapers,
- narration must pass the guard or is replaced by the template (narrate/guard),
- reads are anonymous (ADR-016) — there is no write path.

Honesty contract: empty result -> not_in_graph; term matching nothing ->
not_in_graph naming the term; term matching >1 entity -> ambiguous with the
candidates; question outside the library -> unsupported. Never a guess.
"""
from dataclasses import dataclass, field, asdict

from agent.catalog import Catalog, short
from agent.narrator import (
    Narrator, citation_strings, render_conflicts, template_answer,
)
from agent.operations import OPERATIONS, SlotError
from agent.planner import LLMPlanner
from agent.sparql import FusekiBackend


@dataclass
class Answer:
    status: str            # answered | not_in_graph | ambiguous | unsupported | error
    question: str
    text: str
    operation: str = ""
    slots: dict = field(default_factory=dict)
    shaped: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    narration_source: str = ""   # llm | template | (empty when not narrated)
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _slot_labels(slots: dict, catalog: Catalog) -> str:
    parts = []
    for name, uri in slots.items():
        e = catalog.get(uri)
        parts.append(f"{name}={e.label if e else short(uri)}")
    return ", ".join(parts)


def _validate_slots(op, slots: dict, catalog: Catalog) -> str:
    """Returns an error message, or '' if the slots are safe to execute."""
    known = {**op.required_slots, **op.optional_slots}
    for name in op.required_slots:
        if not slots.get(name):
            return f"the planner did not fill required slot '{name}'"
    for name, uri in slots.items():
        if name not in known:
            return f"unknown slot '{name}' for operation {op.name}"
        entity = catalog.get(uri)
        if entity is None:
            return (
                f"slot '{name}' value {uri!r} is not an entity in the graph "
                "catalog — refusing to query"
            )
        if entity.type != known[name]:
            return (
                f"slot '{name}' must be a {known[name]}, but {entity.label!r} "
                f"is a {entity.type}"
            )
    return ""


def _check_resolution(op, slots: dict, slot_terms: dict, catalog: Catalog):
    """Deterministic backstop on the planner's entity resolution (F6, ADR-019).

    Membership + type checks (above) only catch a URI that is out-of-catalog or
    the wrong kind; they cannot catch a *same-type mis-resolution* (the planner
    filling the TabNet URI for a question it matched as 'XGBoost') or an
    ambiguity it silently collapsed. Here code — not the planner's honor —
    re-derives resolution from the surface term the planner reports:

    * `catalog.find(term)` matching >1 entity -> ambiguous (in code).
    * matching exactly one entity that isn't the planner's URI -> mismatch.
    * matching none (the term isn't a verbatim label/alias) -> unverifiable, so
      leave it: the catalog match is deliberately exact and cannot adjudicate a
      paraphrase, and a false rejection would break legitimate resolutions.

    Returns (status, text) to short-circuit, or None if nothing is provably
    wrong. A slot with no reported term is skipped (our planner supplies them;
    an absent term can't be adjudicated).
    """
    known = {**op.required_slots, **op.optional_slots}
    for name, uri in slots.items():
        if name not in known:
            continue  # handled by _validate_slots
        term = (slot_terms or {}).get(name)
        if not term:
            continue
        cands = catalog.find(term)
        if not cands:
            continue  # term isn't a verbatim label/alias — not adjudicable
        if len(cands) > 1:
            options = "; ".join(f"{c.label} ({short(c.uri)})" for c in cands)
            return ("ambiguous",
                    f"'{term}' matches more than one entity: {options}. "
                    "Please disambiguate.")
        if cands[0].uri != uri:
            ent = catalog.get(uri)
            return ("error",
                    f"resolution mismatch on slot '{name}': the term {term!r} "
                    f"resolves to {cands[0].label!r} ({short(cands[0].uri)}), "
                    f"not {ent.label if ent else short(uri)}.")
    return None


def answer_question(
    question: str,
    backend=None,
    catalog: Catalog = None,
    planner=None,
    narrator: Narrator = None,
) -> Answer:
    backend = backend or FusekiBackend()
    catalog = catalog or Catalog.fetch(backend)
    planner = planner or LLMPlanner()
    narrator = narrator or Narrator()

    # 1. resolve + select (the only LLM step before narration)
    plan = planner.plan(question, catalog)

    if plan.operation == "unsupported":
        return Answer(
            status="unsupported", question=question,
            text="I can't express that with the operations I have yet"
                 + (f": {plan.note}" if plan.note else "."),
            detail=plan.note,
        )

    if plan.unresolved_terms:
        terms = ", ".join(f"'{t}'" for t in plan.unresolved_terms)
        return Answer(
            status="not_in_graph", question=question,
            text=f"The graph has no method, dataset, or metric matching {terms} "
                 "(checked against every label and alias in the catalog).",
            operation=plan.operation, detail=plan.note,
        )

    if plan.ambiguities:
        lines = []
        for amb in plan.ambiguities:
            cands = [catalog.get(u) for u in amb.get("candidates", [])]
            cands = [c for c in cands if c is not None]
            if len(cands) < 2:
                continue  # not a real ambiguity against the catalog
            options = "; ".join(f"{c.label} ({short(c.uri)})" for c in cands)
            lines.append(f"'{amb['term']}' could mean: {options}")
        if lines:
            return Answer(
                status="ambiguous", question=question,
                text="Please disambiguate — " + " | ".join(lines),
                operation=plan.operation, detail=plan.note,
            )

    op = OPERATIONS.get(plan.operation)
    if op is None:
        return Answer(
            status="error", question=question,
            text=f"The planner chose an unknown operation "
                 f"{plan.operation!r}; refusing to proceed.",
        )

    err = _validate_slots(op, plan.slots, catalog)
    if err:
        return Answer(
            status="error", question=question, operation=op.name,
            slots=plan.slots, text=f"Query rejected before execution: {err}.",
        )

    # F6: deterministic resolution backstop (mis-resolution / silent ambiguity).
    res = _check_resolution(op, plan.slots, plan.slot_terms, catalog)
    if res:
        status, text = res
        return Answer(
            status=status, question=question, operation=op.name,
            slots=plan.slots, text=text,
        )

    # 2. execute — code-built SPARQL over validated catalog URIs only
    try:
        sparql = op.build_sparql(plan.slots)
    except SlotError as exc:
        return Answer(
            status="error", question=question, operation=op.name,
            slots=plan.slots, text=f"Query rejected before execution: {exc}.",
        )
    rows = backend.select(sparql)

    if not rows:
        return Answer(
            status="not_in_graph", question=question, operation=op.name,
            slots=plan.slots,
            text="The graph doesn't contain that: no benchmark result matches "
                 f"{_slot_labels(plan.slots, catalog)}.",
        )

    shaped = op.shape(rows, plan.slots, catalog)

    # F2: a cell with more than one result is not a single answer — surface
    # every disagreeing source rather than silently pick one (ADR-018/019).
    if shaped.get("conflicts"):
        return Answer(
            status="multiple_sources", question=question, operation=op.name,
            slots=plan.slots, shaped=shaped, citations=citation_strings(shaped),
            text="The graph holds more than one result for this cell, so a "
                 "single answer would be a guess. " + render_conflicts(shaped),
        )

    # A pairwise comparison where only one side has data is not an answer.
    if shaped["kind"] == "compare_pair" and not shaped["comparisons"]:
        partial = template_answer(shaped)
        return Answer(
            status="not_in_graph", question=question, operation=op.name,
            slots=plan.slots, shaped=shaped,
            citations=citation_strings(shaped),
            text="The graph can't support this comparison — the two methods "
                 "share no (dataset, metric) here. " + partial,
        )

    # F4: seen-vs-unseen with an empty bucket is one-sided, not a comparison.
    if shaped["kind"] == "seen_unseen" and (
            shaped["seen"]["n_datasets"] == 0
            or shaped["unseen"]["n_datasets"] == 0):
        present = "seen" if shaped["seen"]["n_datasets"] else "unseen"
        missing = "unseen" if present == "seen" else "seen"
        return Answer(
            status="not_in_graph", question=question, operation=op.name,
            slots=plan.slots, shaped=shaped, citations=citation_strings(shaped),
            text=f"Can't compare seen vs unseen for {shaped['method_label']}: "
                 f"it has annotated results only on {present} datasets, none "
                 f"{missing} in the graph.",
        )

    # 3. render deterministically (ADR-019); LLM narration is opt-in and never
    #    sees the question.
    text, source = narrator.narrate(shaped)
    return Answer(
        status="answered", question=question, operation=op.name,
        slots=plan.slots, shaped=shaped, text=text,
        citations=citation_strings(shaped), narration_source=source,
    )
