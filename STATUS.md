# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 1 CLOSED → ready for Phase 2 coding.
**Date of last update:** 2026-06-19

Live slice confirmed: Fuseki running, ontology loaded (10 metrics live), 48 BenchmarkResults loaded
(796 total triples). Flagship Gesture query answered with sourced results (8 methods ranked by
cross-entropy loss, all citing "Table 2, p. 6, Shwartz-Ziv & Armon 2022").

Phase 2 plan written in `docs/EXTRACTION_NOTES.md`: vision-assisted extraction (PyMuPDF render +
multimodal LLM on page image), strict-JSON -> deterministic-TTL, validate, queue for review.
Decisions logged as ADR-009 (approach) and ADR-010 (gold = the Phase-1 hand-entry).
**Build-gate lifted:** Phase 2 CODING is now unblocked.

## Done
- [x] Continuity kit + decisions (ADR-001..010).
- [x] Ontology `ontology/mlkg.ttl` written, validated, extended for Phase 1 vocab.
- [x] Phase 0 setup bundle (docker-compose, init_fuseki.sh, load_data.sh, Makefile, query.py).
- [x] Phase 1 data: `data/shwartzziv2022.ttl` (Table 2, 48 results) validated offline (749 triples).
- [x] First eval pairs in `eval/eval_set.jsonl`.
- [x] Phase 2 plan + difficulties tracked in `docs/EXTRACTION_NOTES.md`.
- [x] Phase 0 live: Fuseki confirmed up, ontology loaded, 10 metrics returned from live endpoint.
- [x] Phase 1 live: data loaded (796 triples), Gesture ranking query confirmed on live endpoint.
- [x] fix: init_fuseki.sh fails loudly on missing FUSEKI_ADMIN_PASSWORD.
- [x] ADR-011: paper year sourcing rule (DOI → Zotero → arXiv).

## Next actions (in order)
1. Phase 2 coding: implement pipeline stages in `docs/EXTRACTION_NOTES.md`, smallest first —
   PyMuPDF render → single-page vision extraction → strict-JSON → deterministic-TTL → validate → proposals file.
2. Run extractor on the Shwartz-Ziv page; diff vs gold; report precision/recall (ADR-010).
3. (Deferred) model seen/unseen condition; extend to Table 2's other 5 datasets.

## Open questions / parking lot
- Verify PyMuPDF table-finding + Anthropic API image/PDF input limits before coding Phase 2.
- JSON record schema + normalization strategy (exact-match first; embeddings only if needed).
- Paper year (2021 preprint vs 2022 journal); dataset dedup when a dataset first recurs.

## Known issues / risks
- Conditions not modeled for Shwartz-Ziv (seen/unseen) — honestly flagged :conditionsComplete false.
- Cross-entropy 100x factor stored as printed (cancels within-table; watch across papers).
- Extraction quality is THE risk (vision-vs-text unproven) — validate empirically on the gold page.
- OWL restrictions document but don't enforce required-core; SHACL deferred to Phase 2+.
