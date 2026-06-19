# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 1 CLOSED. Phase 2 = JSON schema FINALISED; ready to implement the first cut.
**Date of last update:** 2026-06-19

Live slice confirmed earlier (Fuseki up, ontology + 48 results live, Gesture query answered with
"Table 2, p.6" citations). Phase 2 design now locked: vision extraction -> strict JSON -> deterministic
TTL -> validate -> review queue. The JSON contract is finalised in `docs/EXTRACTION_NOTES.md`.

Ingestion reframed as a deliberate knowledge-capture ritual (DESIGN "Ingestion philosophy"): speed is
never the goal, correctness is; ~100% per paper; the system raises targeted questions instead of asking
for passive list-approval. Logged as ADR-012 (active review) and ADR-013 (entity identity via raw +
canonical, aliases as skos:altLabel in the graph). Four refinements applied over the draft schema:
identity generalised to method/dataset/metric; aliases live in the graph (not a JSON file); flags are
code-driven (not LLM self-confidence); higher_is_better dropped (direction lives on the :Metric).

## Done
- [x] Continuity kit + decisions (ADR-001..013).
- [x] Ontology written, validated, extended for Phase 1 vocab; live load confirmed.
- [x] Phase 0/1 live slice closed (Fuseki + ontology + 48 results + sourced Gesture query).
- [x] Phase 2 plan + tracked difficulties in `docs/EXTRACTION_NOTES.md`.
- [x] Phase 2 JSON contract finalised; ingestion philosophy + ADR-012/013 written.

## Next actions (in order)
1. Ontology touch: add `skos:` prefix + `skos:prefLabel`/`skos:altLabel` on canonical Method/Dataset/Metric
   individuals in `ontology/mlkg.ttl` (Claude Code, additive change).
   *(Alias strategy is settled by ADR-013: aliases live in the graph as `skos:altLabel`, not a JSON file.
   Reversing this would require a new ADR.)*
2. Build the first vertical cut (Claude Code): render page → vision call → JSON → normalise-against-graph
   → TTL emit → validate → `proposals/<paper>.jsonl` + flag queue. No auto-commit.
3. Run extractor on the Shwartz-Ziv page; diff vs `data/shwartzziv2022.ttl` gold; report precision/recall.
4. (Deferred) model seen/unseen condition; extend to Table 2's other 5 datasets.

## Open questions / parking lot
- Verify PyMuPDF render/find_tables + Anthropic API page-image limits before coding.
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs.

## Known issues / risks
- Conditions still not modeled for Shwartz-Ziv (seen/unseen) — flagged :conditionsComplete false.
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
- Extraction quality is THE risk (vision-vs-text unproven) — validate on the gold page first.
- OWL restrictions document but don't enforce required-core; SHACL deferred.

