# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 2 complete — all 88 results extracted cleanly; proposals ready for Fuseki load.
**Date of last update:** 2026-06-20

Flag resolution is done. All aliases added (6 seen datasets, 5 new unseen datasets minted in
data/shwartzziv2022.ttl, 3 ensemble method altLabels, metric scale-stripping in normaliser).
Re-run: 88/88 clean, 0 flagged. Scorer: 100% recall on seen 48, 100% value + std_error precision.
Spot-check: 8/8 gold pairs correct (no false failures -- now uses exact canonical URI matching).

IMPORTANT BEFORE LOADING -- URI scheme mismatch:
  The proposed TTL uses :prop_* URIs; the original gold uses :r_* URIs.
  Loading proposals/shwartzziv2022_proposed.ttl as-is would add 88 NEW
  BenchmarkResult individuals while the original 48 remain under :r_* URIs
  --> 136 total BenchmarkResults = 48 semantic duplicates.
  Decision needed: load only the 40 NEW (unseen dataset) results, OR replace
  the 48 existing ones, OR accept dual-URI representation for now.

Graph state: 966 triples (ontology 356 + data 610). 48 BenchmarkResults live.
DO NOT load proposals to Fuseki automatically -- decision on URI strategy first.

## Done
- [x] Continuity kit + decisions (ADR-001..013).
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

## Next actions (in order)
1. DECISION: how to handle the URI-scheme mismatch before loading unseen results.
   Option A (recommended): load only the 40 new records (filter by dataset not in original gold).
   Option B: write a one-off script to emit the 40-record subset TTL from proposals JSONL,
             then bash scripts/load_data.sh data/shwartzziv2022_unseen.ttl.
   Option C: Accept dual-URI representation temporarily; fix in a dedup pass later.
2. After decision: load unseen results into Fuseki; confirm BenchmarkResults = 88.
3. Model seen/unseen conditions; extend :conditionsComplete logic.
4. ADR for URI naming convention (extraction-proposed vs hand-reviewed).

## Open questions / parking lot
- URI scheme: :prop_* (extraction) vs :r_* (hand-reviewed) -- needs ADR.
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs in a new paper.

## Known issues / risks
- Conditions still not modeled for Shwartz-Ziv (seen/unseen) -- flagged :conditionsComplete false.
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
- OWL restrictions document but don't enforce required-core; SHACL deferred.
