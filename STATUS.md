# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** 0 CLOSED → ready for Phase 1
**Date of last update:** 2026-06-17

Design locked (RDF/SPARQL, BenchmarkResult-as-atom). Fuseki is running in Docker at
`http://localhost:3030`. Dataset `mlkg` (persistent TDB2) created and ontology loaded.
Smoke query returned 8 metric rows — Phase 0 slice is fully closed.

## Done
- [x] Vision (README), DESIGN, DECISIONS, CLAUDE continuity kit.
- [x] Decisions: RDF/SPARQL (ADR-001), result-as-atom (ADR-002), partial conditions (ADR-003).
- [x] **Turtle ontology `ontology/mlkg.ttl` written + validated.** Five refinements over the sketch:
      metric direction, numeric/text condition values, controlled-vocab condition types,
      functional-core cardinality, conditionsComplete flag. Documented in `docs/ONTOLOGY.md`.
- [x] **Phase 0 slice CLOSED.** Fuseki up (Docker, `stain/jena-fuseki:latest`), dataset `mlkg`
      created (TDB2), ontology loaded, smoke SPARQL query returned 8 metric rows live.
      `.env` created with random FUSEKI_ADMIN_PASSWORD.

## In progress
_(nothing)_

## Next actions (in order)
1. Choose seed paper for Phase 1 (RF/XGBoost-under-noise tabular study fits best).
2. Hand-enter ONE real paper's results as instance triples (`.ttl` file under `data/`, human-reviewed).
3. Run the flagship comparison query against the live Fuseki endpoint to close the Phase 1 slice.

## Open questions / parking lot
- Which seed paper for Phase 1? (an RF/XGBoost-under-noise tabular study fits the example best)
- Dataset-characteristic vs condition overlap (rule of thumb noted in ONTOLOGY.md — watch for dupes).
- Repo name.

## Known issues / risks
- Empty-cathedral risk — mitigated by always-working-slice (ADR-007).
- Extraction quality is the real engineering risk; budget time there, not on ontology polish.
- OWL restrictions document but do not enforce required-core; SHACL enforcement deferred to Phase 2+.
