# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 2 — real vision extraction complete; flag resolution pending.
**Date of last update:** 2026-06-19

Real extraction ran end-to-end: stop_reason=end_turn, 12,562 output tokens (16,384 limit).
88 results extracted (8 methods x 11 datasets: 6 seen + 5 unseen). All 88 flagged (0 clean).
Previous run was truncated at 8,192 max_tokens; fixed by raising to 16,384 + compact JSON prompt.

Flag breakdown:
  no_alias_match:      121  (all 11 datasets unresolved; 3 method variants unresolved)
  metric_not_in_vocab:  72  (all "cross-entropy loss x100" cells; MSE cells resolve fine)

Value spot-check (8 gold pairs): 7/8 match gold exactly. Note: 2 "failures" are false misses --
the spot-check substring-matches "xgboost" inside "Deep Ensemble w/ XGBoost", so the Deep Ensemble
rows are being compared to the wrong gold value. Actual extracted values (78.93 and 93.50) are correct.

Graph state: 926 triples (ontology + SKOS + data), 48 BenchmarkResults. .env gitignored.
DO NOT load proposals to Fuseki automatically -- only load after flag resolution + human review.

## Done
- [x] Continuity kit + decisions (ADR-001..013).
- [x] Ontology written, validated, extended for Phase 1 vocab; live load confirmed.
- [x] Phase 0/1 live slice closed (Fuseki + ontology + 48 results + sourced Gesture query).
- [x] Phase 2 plan + tracked difficulties in `docs/EXTRACTION_NOTES.md`.
- [x] Phase 2 JSON contract finalised; ingestion philosophy + ADR-012/013 written.
- [x] SKOS aliases added to `ontology/mlkg.ttl`; reloaded into Fuseki.
- [x] Phase 2 first cut built (`scripts/phase2_extract.py`); pipeline validated end-to-end via mock.
- [x] Gold-diff scorer built (`scripts/eval_extraction.py`); smoke-tested against mock proposals.
- [x] Real vision extraction complete: 88 records, no truncation, proposals/shwartzziv2022.jsonl updated.

## Next actions (in order)
1. Resolve flags -- add `skos:altLabel` to `ontology/mlkg.ttl` for:
   Datasets: "Rossman" -> `:ds_rossmann`, "CoverType" -> `:ds_covertype`, "Higgs" -> `:ds_higgs`,
             "Gas" -> `:ds_gas`, "Eye" -> `:ds_eye`, "Gesture" -> `:ds_gesture`,
             "YearPrediction", "MSLR", "Epsilon", "Shrutime", "Blastchar" (5 unseen -- new entities or aliases)
   Methods:  "Simple Ensemble" -> `:SimpleEnsemble_sz2022`,
             "Deep Ensemble w/o XGBoost" -> `:DeepEnsemble_noXGB_sz2022`,
             "Deep Ensemble w XGBoost" -> `:DeepEnsemble_XGB_sz2022`
   Metric:   "cross-entropy loss x100" -> `:CrossEntropyLoss` (via altLabel; strip ×100 later)
   Reload ontology into Fuseki after changes: see CLAUDE.md GSP endpoint.
2. Re-run extraction after alias resolution:
   `python scripts/phase2_extract.py`
   Then score: `python scripts/eval_extraction.py proposals/shwartzziv2022.jsonl`
3. (Deferred) model seen/unseen condition; fix spot-check false-miss for Deep Ensemble names.

## Open questions / parking lot
- Verify PyMuPDF render/find_tables + Anthropic API page-image limits before coding.
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs.

## Known issues / risks
- Conditions still not modeled for Shwartz-Ziv (seen/unseen) — flagged :conditionsComplete false.
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
- Extraction quality is THE risk (vision-vs-text unproven) — validate on the gold page first.
- OWL restrictions document but don't enforce required-core; SHACL deferred.

