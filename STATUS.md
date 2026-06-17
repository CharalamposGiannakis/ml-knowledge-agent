# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** 0 (Skeleton & ontology) — design locked, repo foundation being laid.
**Date of last update:** (fill in)

Design is settled. Knowledge store = RDF/SPARQL on Jena Fuseki. Atom = BenchmarkResult, not
Comparison. Continuity kit (this file, DESIGN, DECISIONS, CLAUDE) created. No code yet.

## Done
- [x] Vision (README) written.
- [x] Knowledge-store decision: RDF/SPARQL (ADR-001).
- [x] Data model: result-as-atom (ADR-002), conditions partial-allowed (ADR-003).
- [x] Continuity kit created (DESIGN.md, DECISIONS.md, STATUS.md, CLAUDE.md).

## In progress
- [ ] Real Turtle ontology → `docs/ONTOLOGY.md` (refine the sketch in DESIGN.md).
- [ ] Fuseki up locally with the ontology loaded.

## Next actions (in order)
1. Write the Turtle ontology from the DESIGN.md sketch.
2. Stand up Fuseki, load the ontology, run a trivial SPARQL query (Phase 0 slice).
3. Hand-enter ONE paper's results as triples; answer one real question with a citation (Phase 1).

## Open questions / parking lot
- Which 1–3 seed papers to start with? (tabular RF vs XGBoost comparisons are a good fit for the README example)
- Condition vocabulary: do we predefine condition types (label_noise, n_rows, class_imbalance...) or let them emerge?
- Repo name.

## Known issues / risks
- Empty-cathedral risk (lots of infra, little data) — mitigated by always-working-slice (ADR-007).
- Extraction quality is the real engineering risk; budget time there, not on ontology polish.
