# DESIGN — ML Engineering Knowledge Agent

> Source of truth for architecture and data model. The README holds the *vision*;
> this file holds the *decisions in force*. If code and this file disagree, this file
> is wrong and should be updated — it must always reflect reality.

---

## Guiding principle

Three goals carry equal weight: **CV/interview impact**, **a tool I actually use**, and
**learning the semantic-web stack deeply**. When they conflict, balance them — but one
discipline protects all three:

**There must always be a working end-to-end slice.** Infrastructure that cannot yet answer
a real question is worth less than an ugly pipeline that can. We chose RDF/SPARQL knowing it
adds complexity; this rule is the counterweight that stops the project becoming a beautiful
empty cathedral (gorgeous ontology, four papers in it, abandoned).

---

## Ingestion philosophy

Ingestion is not a pipeline to be optimised for speed. It is a deliberate knowledge-capture
session — one paper at a time, with the human as an active participant, not a passive approver.

The long-term use case: papers have to be read anyway, for study and for work. Ingestion turns that
reading into permanent, queryable knowledge — it replaces "I read this once and half-forgot it" with
"this is in the graph and citable forever." That value is what justifies taking the time to do it
properly, and it is the motivation to stay on a paper's results instead of scrolling past them.

**Consequences that govern every ingestion decision:**

- **Speed is never a goal for ingestion. Correctness is the only goal.** If a paper takes 45 focused
  minutes to ingest well, that is fine — it is ingested once, and every answer about it is trustworthy forever.
- **The system must never silently resolve an ambiguous decision.** When it cannot determine method
  identity, dataset identity, metric scope, or condition completeness with certainty, it raises a
  specific, targeted question and waits for a human answer.
- **Approving an unambiguous record is one keypress; resolving an ambiguous one is a deliberate choice.**
- **Every question the system raises is an invitation to read more carefully** about what the paper
  actually claims. The review session is part of the reading, not overhead on top of it.
- **One wrong triple in the graph is a real problem; one paper not yet ingested is not.** Precision
  over coverage, always. The quality bar is ~100% per paper, not X% across thousands.

This principle governs everything downstream of it: the extraction prompt, the JSON schema, the
normalisation step, the review UI, and the question-raising mechanism (see ADR-012, ADR-013).

---

## The data model (the one decision everything hangs on)

### The atom is a *result*, not a *comparison*

The stored unit is a single **BenchmarkResult**:

```
(method, dataset, metric, value, conditions, source)
```

A **comparison** is *not stored*. It is derived at query time by finding two results that
share the same dataset + metric + matching conditions and diffing their values.

Why result-as-atom and not comparison-as-atom:
- Papers compare N methods in one table; pairwise storage explodes combinatorially or loses info.
- It is faithful to what papers literally print (rows of results), not an author's chosen pairings.
- The agent can compare *any* two methods sharing conditions — not only the pairs an author highlighted.

### Ontology shape (illustrative — authoritative source is `ontology/mlkg.ttl`)

> This is a **conceptual summary only**. The live schema is `ontology/mlkg.ttl`; design
> rationale and refinements (including the five deliberate upgrades over this sketch) are in
> `docs/ONTOLOGY.md`. Do not use this summary as a coding reference — the live ontology differs
> in important ways (e.g. `:conditionType` is an `ObjectProperty → :ConditionType` individual,
> conditions split into `conditionValueNum`/`conditionValueText`/`conditionUnit`, SKOS alias
> support is added on canonical individuals).

**Core shape:**
- **`:BenchmarkResult`** (the atom) links `:reportsMethod`, `:onDataset`, `:usesMetric`,
  `:hasValue`, `:hasSource` — all `owl:FunctionalProperty`.
- **`:underCondition`** → `:Condition` nodes (typed via `:conditionType → :ConditionType`
  individual from a controlled vocabulary; value split into numeric/text paths for range queries).
- **`:SourceLocation`** → `:locator` (e.g. "Table 2"), `:page`, `:fromPaper → :Paper`.
- **`:Metric`** carries `:optimizationDirection` (`:HigherIsBetter` / `:LowerIsBetter`).
- **`:Paper`** carries `:title`, `:year`, `:doi`.

### Comparison as a query (illustrative)

```sparql
SELECT ?mA ?vA ?mB ?vB ?src WHERE {
  ?rA :reportsMethod ?mA ; :onDataset ?d ; :usesMetric ?metric ; :hasValue ?vA ; :hasSource ?src .
  ?rB :reportsMethod ?mB ; :onDataset ?d ; :usesMetric ?metric ; :hasValue ?vB .
  ?rA :underCondition [ :conditionType "label_noise" ; :conditionValue ?n ] .
  FILTER(?mA != ?mB)
}
```

### Conditions: required as a concept, partial allowed

Hard-required core for any result to enter the graph: **method, dataset, metric, value, source.**
Conditions are strongly encouraged and captured whenever present, but a result with *partial*
conditions is **accepted-and-flagged**, not rejected. Real papers are sloppy; a too-rigid schema
rejects most real extractions. The flag lets the agent caveat its answers honestly.

---

## Architecture

```
PDF ──▶ Extraction (LLM) ──▶ proposed triples ──▶ HUMAN REVIEW (accept/edit/reject)
                                                          │
                                                          ▼
                                              Triple store (Jena Fuseki)  ◀── SPARQL
                                                          │
                          Vector store (ChromaDB) ◀───────┘  (abstracts + condition text)
                                                          │
                                              Agent (Anthropic API + tools)
                                              chooses SPARQL / semantic / both
                                                          │
                                                  Minimal chat UI
                                            (query mode | ingest-review mode)
```

The **human review step is a built feature, not a chore**: a small UI shows proposed triples next
to the source PDF region. The accept/edit/reject log doubles as a labeled dataset for measuring
extraction precision.

---

## Reliability must be measured, not asserted

The README's whole pitch is "no hallucination." That claim is only credible if measured.
Build a small **eval set** (~30 question → expected-source pairs) early and report:
- retrieval precision (did it find the right result?)
- citation accuracy (did it cite the right table/paper?)

This is the line that turns a demo into a system in an interview.

---

## Stack (unchanged from README, confirmed)

| Component        | Tech                              |
|------------------|-----------------------------------|
| PDF parsing      | PyMuPDF                           |
| Extraction       | Anthropic API (Opus)              |
| Knowledge graph  | OWL/RDF + Apache Jena Fuseki      |
| Vector store     | ChromaDB                          |
| Backend          | FastAPI                           |
| Agent            | Anthropic API with tool use       |
| Frontend         | Vanilla JS                        |

---

## Build phases (each ends with a working slice)

- **Phase 0 — Skeleton & ontology.** Repo + continuity kit. Real Turtle ontology in `ONTOLOGY.md`.
  Fuseki running, ontology loaded. *Slice: SPARQL query returns nothing, but runs.*
- **Phase 1 — Thin vertical slice.** Hand-enter ONE paper's results as triples. Agent answers one
  real question with a real citation. *Slice: end-to-end works on 1 paper, zero pipeline.*
- **Phase 2 — Extraction pipeline.** PyMuPDF + LLM proposes triples from a PDF; writes `proposals/<paper>.jsonl` + flag queue for review (no auto-commit).
- **Phase 3 — Review UI.** Accept/edit/reject proposals into the graph. Log decisions.
- **Phase 4 — Agent routing.** SPARQL vs semantic search vs both; merge; sourced answer.
- **Phase 5 — Eval.** ~30 Q→source pairs; report retrieval + citation accuracy.

Folders are added when a phase needs them. No empty folders ahead of time.
