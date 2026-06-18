# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** 1 CLOSED — moving to Phase 2 planning.
**Date of last update:** 2026-06-18

Seed paper fully loaded live. `data/shwartzziv2022.ttl` (Table 2, 6 datasets, 48 BenchmarkResults)
POSTed into Fuseki; live count confirmed = 48. Gesture cross-entropy ranking query verified against
the live endpoint: Deep Ensemble w/ XGBoost (78.93) ranks 1st, XGBoost (80.64) 2nd, both citing
"Table 2" p.6 of Shwartz-Ziv & Armon 2022. All source provenance resolves correctly.

## Done
- [x] Continuity kit + decisions (ADR-001..007).
- [x] Ontology `ontology/mlkg.ttl` written, validated, and extended for Phase 1 vocab.
- [x] Phase 0 setup bundle (docker-compose, init_fuseki.sh, Makefile, query.py).
- [x] Seed paper ingested offline: `data/shwartzziv2022.ttl` (Table 2, 48 BenchmarkResults,
      values + stdError, dataset characteristics). All flagged :conditionsComplete false.
- [x] First eval pairs in `eval/eval_set.jsonl`.
- [x] Phase 0 live: Fuseki up, ontology loaded (10 metrics; smoke query passed).
- [x] Phase 1 live: `data/shwartzziv2022.ttl` loaded (48 BenchmarkResults confirmed); Gesture
      cross-entropy ranking query verified — Deep Ensemble w/ XGBoost (78.93) 1st, XGBoost
      (80.64) 2nd, both sourced to Table 2 p.6.

## Next actions (in order)
1. Refinement pass: model the seen-vs-unseen dataset condition (flip :conditionsComplete where done).
2. Optionally extend to Table 2's other 5 datasets (note: YearPrediction = MSE, others cross-entropy).
3. Phase 2 planning: extraction pipeline (PyMuPDF + LLM) — see EXTRACTION_NOTES.

## Open questions / parking lot
- Paper year: source PDF is arXiv:2106.03253v2 (Nov 2021); :year set to 2022 (Information Fusion). Confirm.
- Dataset dedup: Higgs/CoverType etc. will recur in later papers — promote datasets to a shared
  reference file then, and decide how to handle per-paper characteristic differences (size/split).
- Should source PDFs be committed at all? (copyright/size — recommend gitignoring `pdfs/`).

## Known issues / risks
- Conditions not yet modeled for this paper (seen/unseen) — honestly flagged, not closed.
- Cross-entropy values carry a 100x factor (Table 2 caption); stored as printed, factor cancels
  within-table. Watch when comparing across papers.
- OWL restrictions document but don't enforce required-core; SHACL deferred to Phase 2+.
