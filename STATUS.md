# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 2 closed — 88 BenchmarkResults live in Fuseki under deterministic IRI scheme.
**Date of last update:** 2026-06-22

ADR-014 decided and implemented: emit_ttl now mints IRIs as
  :r_{paper_id}__{method_local}__{dataset_local}__{metric_local}
Same result -> same IRI -> idempotent loads, no duplicates confirmed.

data/shwartzziv2022_full.ttl generated: 88 BenchmarkResults + full metadata (paper, 11 datasets,
3 ensemble methods, SKOS aliases). data/shwartzziv2022.ttl FROZEN as eval gold (48 records).

Graph state: 1233 triples (ontology 356 + full data 877). 88 BenchmarkResults live, 0 duplicates.
Flagship query confirmed: XGBoost/Gesture/CE = 80.64 +/- 0.80.

Scorer: 48/48 gold recall, 100% P/R all fields on adjudicable pairs. 40 beyond-gold records
correctly labelled (5 unseen datasets) and excluded from precision denominator.

## Done
- [x] Continuity kit + decisions (ADR-001..014).
- [x] Ontology written, validated, extended for Phase 1 vocab; live load confirmed.
- [x] Phase 0/1 live slice closed (Fuseki + ontology + 48 results + sourced Gesture query).
- [x] Phase 2 plan + tracked difficulties in `docs/EXTRACTION_NOTES.md`.
- [x] Phase 2 JSON contract finalised; ingestion philosophy + ADR-012/013 written.
- [x] SKOS aliases added to `ontology/mlkg.ttl`; reloaded into Fuseki.
- [x] Phase 2 first cut built (`scripts/phase2_extract.py`); pipeline validated end-to-end via mock.
- [x] Gold-diff scorer built (`scripts/eval_extraction.py`); smoke-tested, then run on real proposals.
- [x] max_tokens raised to 16384 + compact JSON instruction; full 88-record extraction confirmed.
- [x] Flag resolution: 6 seen dataset altLabels, 5 new unseen datasets minted, 3 method altLabels,
      metric scale-stripping (_METRIC_SCALE_RE) in normaliser.
- [x] Re-run post-resolution: 88/88 clean, scorer 100% recall + 100% value precision on seen 48.
- [x] Spot-check bug fixed: exact canonical URI matching (was: substring, caused false failures).
- [x] ADR-014: deterministic IRI scheme; emit_ttl updated; data/shwartzziv2022_full.ttl generated.
- [x] Fuseki clean-reloaded: ontology + shwartzziv2022_full.ttl only; 88 BenchmarkResults, 0 dups.
- [x] Scorer precision fixed: 40 beyond-gold records excluded from precision denominator (100% P/R).
- [x] GIT DISCIPLINE rule added to CLAUDE.md.
- [x] ADR-015: ontology health harness built (SHACL gate + SPARQL invariants + OWL consistency).
      scripts/validate_shapes.py, healthcheck.py, consistency.py; load_data.sh gates on SHACL;
      Makefile targets validate/load-data/healthcheck/consistency added.

## Next actions (in order)
1. Add second paper to the corpus; run full Phase 2 pipeline (render -> vision -> normalise -> review).
2. Model conditions properly for Shwartz-Ziv (seen/unseen split) -- :conditionsComplete is false for all 88.
3. Build the Phase 3 query agent (SPARQL dispatch from natural language, FastAPI endpoint).

## Open questions / parking lot
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs in a new paper.

## Known issues / risks
- Conditions still not modeled for Shwartz-Ziv (seen/unseen) -- flagged :conditionsComplete false.
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
