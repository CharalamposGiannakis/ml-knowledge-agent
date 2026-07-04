# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**Phase:** Phase 2 closed — 88 BenchmarkResults live in Fuseki under deterministic IRI scheme.
Acted on an external audit (`docs/fable.md`) of the health harness + extraction pipeline;
mechanical fixes only. Then diagnosed and fixed a Fuseki connection-loop regression caused by
the audit's own image-pin change (see below). Verified end-to-end: 88 BenchmarkResults live,
all 8 healthcheck invariants green. ADR-016 (proportionate strictness) recorded. This work,
plus this documentation sync, is committed.
**Date of last update:** 2026-07-04

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
- [x] Continuity kit + decisions (ADR-001..016).
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
- [x] Audit response (this session, ADR-015 revised): SHACL gate had `inference="rdfs"`, which
      made every `sh:class` check vacuous (RDFS closure over `rdfs:range` invents the type the
      shape then checks for) — confirmed empirically two ways it silently passed bad data
      (dangling dataset URI, a Method plugged into `:onDataset`). Fixed to `inference="none"`;
      added DatasetShape/MethodShape (require rdfs:label). Layer 3's `owlrl` consistency check
      was verified to report CONSISTENT over both a cross-typed individual and a multi-valued
      `:hasValue` — removed `scripts/consistency.py` and the `owlrl` dependency entirely;
      replaced with plain SPARQL invariants (checks E-H) in `healthcheck.py`. Added `tests/`
      (38 tests: 3 adversarial SHACL fixtures, the new invariants, `phase2_extract.py`'s pure
      functions, the scorer's key-matching) and a pinned `requirements.txt`. Extraction hygiene:
      `temperature=0`, `PROMPT_VERSION` constant, `extracted_by` derived from `MODEL` (was
      copied from the schema template), timestamped raw-output files, fixed a no-op
      `.replace("±","±")`, extended `_parse_cell` for negatives/%/unicode minus, added a
      `value_unverifiable` flag when a cell can't be parsed (previously trusted blind). Hygiene:
      pinned the Fuseki image (`daschswiss/apache-jena-fuseki:5.5.0-3`, was unpinned `:latest`
      on a dormant Jena 3.x-era image), removed `admin` password fallbacks, added `.claude/` to
      `.gitignore`, renamed `env.example` -> `.env.example` to match the documented setup
      command, added a "GOLD — never load" banner to `data/shwartzziv2022.ttl`. Fuseki admin
      password (was committed in `.claude/settings.local.json`): **RESOLVED** — rotated by the
      user. Full findings in `docs/fable.md`; deliberately out of scope (needs design, not
      mechanics): condition-hash IRI migration, PAPER_META de-hardcoding, value-scale ADR,
      review-decision log.
- [x] Fixed the Fuseki connection-loop regression the image pin (above) introduced. Root causes,
      in the order actually found: (1) the image pin edited docker-compose.yml but the running
      container was never recreated — it kept serving on `stain/jena-fuseki` 2 weeks stale, so
      anything expecting the new image/behavior was talking to the old one; a plain `docker
      compose up -d` does not recreate a running container on a compose-file edit alone. (2) The
      admin password in `.env` had in fact never been rotated (still the same value leaked in
      `.claude/settings.local.json` last session) — confirmed by comparing values programmatically
      without printing either. (3) A real, independent regression: `daschswiss/apache-jena-fuseki`'s
      stock `shiro.ini` denies anonymous SPARQL query (`/** = authcBasic,user[admin]` catches
      `/mlkg/query`), unlike whatever the old `stain` image was configured with — broke
      `scripts/query.py`, `healthcheck.py`, and the trailing queries in `init_fuseki.sh`/
      `load_data.sh`, all of which hit `/query` unauthenticated by design (the future read-only
      query agent must not need admin credentials for a SELECT). Fixed by mounting a custom
      `fuseki-shiro.ini` over the image's stock template (`$FUSEKI_HOME/shiro.ini`, not the
      `$FUSEKI_BASE` volume) opening `/*/query` and `/*/sparql` to anon while keeping every
      write/admin path authenticated. Hit one self-inflicted snag along the way: the custom
      file's own explanatory comments contained the literal substring the entrypoint's
      placeholder sanity check greps the whole file for, causing a real crash-loop of its own
      until reworded. `init_fuseki.sh`/`load_data.sh` now decode HTTP status codes explicitly
      (401 fails fast with a no-retry message pointing at `FUSEKI_ADMIN_PASSWORD`; 404 on the
      dataset either creates it (`init_fuseki.sh`) or points at `init_fuseki.sh` (`load_data.sh`);
      connection-refused stays a single bounded wait, already the case for the ping loop).
      Verified end-to-end post-fix: unauthenticated SELECT on `/mlkg/query` -> 200, unauthenticated
      GSP write -> 401, `init_fuseki.sh` -> `load_data.sh data/shwartzziv2022_full.ttl` (SHACL
      gate passes) -> `healthcheck.py` all green, COUNT(:BenchmarkResult)=88. Fuseki admin
      password: **RESOLVED** — rotated by the user.
- [x] ADR-016 recorded (proportionate strictness: minimal enforced invariants, permissive schema
      + read-open/write-gated store, tighten only on demonstrated failure).
- [x] ADR-017 recorded + implemented: seen/unseen modeled as an optional annotation
      (`:datasetSeenByModel` in {"seen","unseen"}) on the 44 deep-model BenchmarkResults
      (TabNet/DNF-Net/NODE seen on their 3 provenance datasets each, unseen elsewhere;
      1D-CNN unseen on all 11); XGBoost + the 3 ensembles left unannotated (N/A). No IRI
      changes (88 IRIs diffed identical before/after). `:conditionsComplete` flipped to
      true on all 88. SHACL shape (optional `sh:in`) + healthcheck invariant I added.
      Clean-reloaded; all 9 healthcheck invariants green; flagship XGBoost/Gesture/CE=80.64
      confirmed; 38/38 tests still pass.

## Next actions (in order)
1. IRI condition-slug — deferred to paper #2's noise condition (ADR-017).
2. Build the query agent (Phase 3/4 vertical slice): natural-language question -> SPARQL ->
   sourced answer, on the now-stable IRI scheme. Design with Opus, then implement. Priority:
   a bigger graph you can't query is the empty-cathedral failure (ADR-007, audit).
3. Add paper #2 through the honest gate; measure via sampled back-verification + a persisted
   review-decision log.

## Open questions / parking lot
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs in a new paper.
- Value-scale policy (audit M2): stored-as-printed ×100 factors will silently miscompare
  against an unscaled paper #2 — needs an ADR before the next paper lands.
- Persisted review-decision log (audit H3/ADR-004): no accept/edit/reject log exists yet;
  "measured, not asserted" reliability only holds for paper #1's hand-made gold.

## Known issues / risks
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
