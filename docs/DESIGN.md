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

### Ontology sketch (to be refined into real Turtle in `docs/ONTOLOGY.md`)

```turtle
@prefix :    <http://mlkg.local/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:<http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# --- Core classes ---
:Paper           a owl:Class .
:Method          a owl:Class .
:MethodFamily    a owl:Class .
:Dataset         a owl:Class .
:Metric          a owl:Class .
:BenchmarkResult a owl:Class .   # THE ATOM
:Condition       a owl:Class .   # reified so conditions are queryable
:SourceLocation  a owl:Class .   # table/figure/page within a paper

# --- BenchmarkResult wiring ---
:reportsMethod  a owl:ObjectProperty ;   rdfs:domain :BenchmarkResult ; rdfs:range :Method .
:onDataset      a owl:ObjectProperty ;   rdfs:domain :BenchmarkResult ; rdfs:range :Dataset .
:usesMetric     a owl:ObjectProperty ;   rdfs:domain :BenchmarkResult ; rdfs:range :Metric .
:hasValue       a owl:DatatypeProperty ; rdfs:domain :BenchmarkResult ; rdfs:range xsd:decimal .
:underCondition a owl:ObjectProperty ;   rdfs:domain :BenchmarkResult ; rdfs:range :Condition .
:hasSource      a owl:ObjectProperty ;   rdfs:domain :BenchmarkResult ; rdfs:range :SourceLocation .

# --- Conditions: typed + value (flexible, queryable) ---
:conditionType  a owl:DatatypeProperty ; rdfs:domain :Condition ; rdfs:range xsd:string .  # "label_noise"
:conditionValue a owl:DatatypeProperty ; rdfs:domain :Condition .                            # "30%" / number / range

# --- Provenance ---
:fromPaper a owl:ObjectProperty ;   rdfs:domain :SourceLocation ; rdfs:range :Paper .
:locator   a owl:DatatypeProperty ; rdfs:domain :SourceLocation ; rdfs:range xsd:string .   # "Table 3"
:page      a owl:DatatypeProperty ; rdfs:domain :SourceLocation ; rdfs:range xsd:integer .

# --- Taxonomy + metadata ---
:inFamily a owl:ObjectProperty ;   rdfs:domain :Method ; rdfs:range :MethodFamily .
:title    a owl:DatatypeProperty ; rdfs:domain :Paper  ; rdfs:range xsd:string .
:year     a owl:DatatypeProperty ; rdfs:domain :Paper  ; rdfs:range xsd:integer .
:doi      a owl:DatatypeProperty ; rdfs:domain :Paper  ; rdfs:range xsd:string .
```

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
- **Phase 2 — Extraction pipeline.** PyMuPDF + LLM proposes triples from a PDF (printed to console).
- **Phase 3 — Review UI.** Accept/edit/reject proposals into the graph. Log decisions.
- **Phase 4 — Agent routing.** SPARQL vs semantic search vs both; merge; sourced answer.
- **Phase 5 — Eval.** ~30 Q→source pairs; report retrieval + citation accuracy.

Folders are added when a phase needs them. No empty folders ahead of time.
