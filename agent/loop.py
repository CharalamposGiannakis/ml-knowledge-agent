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
from agent.narrator import Narrator, citation_strings, template_answer
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

    shaped = op.shape(rows, plan.slots)

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

    # 3. narrate + guard
    text, source = narrator.narrate(question, shaped)
    return Answer(
        status="answered", question=question, operation=op.name,
        slots=plan.slots, shaped=shaped, text=text,
        citations=citation_strings(shaped), narration_source=source,
    )
