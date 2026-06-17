# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** 0 (Skeleton & ontology) — ontology written and validated; Fuseki not yet stood up.
**Date of last update:** (fill in)

Design locked (RDF/SPARQL, BenchmarkResult-as-atom). The Turtle ontology exists as
`ontology/mlkg.ttl` and is validated (parses to 289 triples; flagship comparison query runs and
reproduces the README's RF-vs-XGBoost example). Documented in `docs/ONTOLOGY.md`. No backend code yet.

## Done
- [x] Vision (README), DESIGN, DECISIONS, CLAUDE continuity kit.
- [x] Decisions: RDF/SPARQL (ADR-001), result-as-atom (ADR-002), partial conditions (ADR-003).
- [x] **Turtle ontology `ontology/mlkg.ttl` written + validated.** Five refinements over the sketch:
      metric direction, numeric/text condition values, controlled-vocab condition types,
      functional-core cardinality, conditionsComplete flag. Documented in `docs/ONTOLOGY.md`.

## In progress
- [ ] Stand up Apache Jena Fuseki locally; load `ontology/mlkg.ttl`.

## Next actions (in order)
1. Run Fuseki (Docker is simplest), create dataset `mlkg`, load `ontology/mlkg.ttl`.
2. Run a trivial SPARQL query against Fuseki's endpoint to close the **Phase 0 slice**.
3. Hand-enter ONE real paper's results as instance triples; run the flagship comparison query
   against the live endpoint (Phase 1 slice).

## Open questions / parking lot
- Which seed paper for Phase 1? (an RF/XGBoost-under-noise tabular study fits the example best)
- Dataset-characteristic vs condition overlap (rule of thumb noted in ONTOLOGY.md — watch for dupes).
- Repo name.

## Known issues / risks
- Empty-cathedral risk — mitigated by always-working-slice (ADR-007).
- Extraction quality is the real engineering risk; budget time there, not on ontology polish.
- OWL restrictions document but do not enforce required-core; SHACL enforcement deferred to Phase 2+.
