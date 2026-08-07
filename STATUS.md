# STATUS — Project Handoff

> **How to use this file:** at the end of a working session, update the three sections below.
> To resume in a fresh chat, paste this whole file as your first message and say "continue from here."
> This is the project's working memory across chats. Keep it short and current.

---

## Where we are
**v1 COMPLETE — portfolio-ready.** One paper fully ingested (Shwartz-Ziv & Armon 2022, 88
BenchmarkResults, deterministic IRIs). Query agent built (ADR-018) and HARDENED against an
independent red-team of the query layer (`docs/redteam.md` → ADR-019): natural-language question
-> operation choice -> code-built SPARQL -> **deterministically-rendered** sourced answer, LLM
writes neither the SPARQL nor the answer sentence. 81/81 tests green (incl. 22 red-team
regression tests, no xfail remaining). CLI + FastAPI route share one loop.
**Eval:** checks are claim-local and score the rendered answer (F5); 2 adversarial one-sided
items included (20 total). **Live eval re-run 2026-07-06** against Fuseki (88-result graph,
healthcheck all 9 invariants green) + live planner: **retrieval 20/20 (100%), citation 13/13
(100%)**, `python eval/run_eval.py`, all 20 items PASS. Separately spot-checked 6 questions
end-to-end via the CLI (`--explain`), one per shape — flagship compare_pair (XGBoost beats
TabNet on Gesture, 80.64 vs 96.42, Table 2 p.6), seen_unseen (TabNet 1.33 vs 6.0 mean rank),
lookup_result (XGBoost/Gesture/CE = 80.64 ± 0.80), not_in_graph (LightGBM vs XGBoost — no
LightGBM results, partial XGBoost value surfaced as caveat), adversarial one-sided seen_unseen
refusal (1D-CNN, F4 — annotated unseen on all 11 datasets, refused rather than one-sided), and
ambiguous entity resolution ("the ensemble" -> 3 candidates listed). All 6 rendered answers
correct with the right citation. No `multiple_sources` case exists to spot-check yet — verified
by direct SPARQL (`GROUP BY method,dataset,metric HAVING COUNT(?r)>1`) that the single-paper
88-result graph has zero cells with >1 result, consistent with ADR-014's dedup-by-construction;
that status path stays covered by its existing unit/red-team tests only until paper #2 lands.
**CI is green on both jobs**: the offline pytest suite, and a live `graph-pipeline` job that
stands up a real Fuseki (this repo's actual `docker-compose.yml`, shiro mount included) and runs
the deterministic half of the pipeline end-to-end — SHACL gate, load, all 9 healthcheck
invariants, the 88-BenchmarkResult count, and the anon-read/auth-write security posture
(ADR-016). Repo hygiene landed: MIT license, CI workflow, README badge, gitignore hygiene.
**Date of last update:** 2026-08-06

**Since v1 (2026-08-06):** Two things resolved. A real, precisely-reproducible
Fuseki ontology-reload bug was root-caused (not yet fixed — full detail in
Done, fix candidates in Backlog); it does not affect a first-time clone-and-run.
A web UI was built, manually tested end-to-end against the live graph, and
merged to main (`feature/web-ui`, see Done).

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
- [x] ADR-018 recorded + query agent built (`agent/` package): the LLM resolves entities against
      the catalog (rdfs:label/skos:altLabel, ADR-013), selects one of 4 hand-written parameterised
      SPARQL operations (compare_pair, best_on_dataset, lookup_result, seen_unseen), and narrates;
      code validates slots (catalog membership + type + URI shape), builds/executes SPARQL
      anonymously (ADR-016), derives winners from :optimizationDirection, and guards narration
      (every number must exist in the returned rows; exact "<locator>, p.<page>" citation
      required; failed guard falls back to the deterministic template). Honest statuses:
      not_in_graph / ambiguous / unsupported; one-sided comparisons are refused with the partial
      fact + citation. CLI (`python -m agent`) + FastAPI (`agent/api.py`, POST /ask) share the
      loop. Eval harness (`eval/run_eval.py`, eval_set.jsonl grown 2 -> 18 items incl. honest-
      refusal/ambiguity/unsupported cases): 18/18 retrieval, 13/13 citation accuracy, live.
      Tests 38 -> 59 (direction both ways, empty result, alias/unknown-term resolution,
      SPARQL-injection slot rejection, guard, seen/unseen ranks, API smoke), all green.
      Note: Opus 4.8 rejects the `temperature` param (deprecated) — planner/narrator calls
      send none.
- [x] Red-team of the query layer + ADR-019 hardening (this session). Independent red-team
      (`docs/redteam.md`) broke the sourced/non-fabricated guarantee at the semantic layer;
      structural boundary (seam-3 injection) held. Fixes, no guard weakened: **F1** ADR-019 —
      the default answer is rendered deterministically by code from the verified payload; free
      LLM narration removed from the default path (opt-in `--llm-narration` only) and the
      untrusted question never enters a narrator prompt; the provenance guard kept as
      defense-in-depth. **F2** cross-paper conflation — a (method,dataset,metric) cell with >1
      result now returns `multiple_sources` naming every source, `ORDER BY` made source-stable.
      **F3** `seen_unseen` labels the queried method, not `rows[0]`. **F4** one-sided seen/unseen
      refused like one-sided compare. **F5** eval scores the rendered answer with claim-local
      value/citation checks + 2 adversarial items. **F6** planner reports each slot's surface
      term; code re-derives resolution (`catalog.find`) to catch same-type mis-resolution and
      collapse silent ambiguity. Tests 59 -> 81 (22 red-team regressions, all passing).
- [x] ADR-019 hardening landed (reviewed and committed — the six red-team fixes above, F1-F6).
- [x] Repo hygiene: MIT license, CI workflow (`test` job), README CI badge, `.gitignore` cleanup.
- [x] Fuseki-in-CI: second CI job (`graph-pipeline`) runs the pipeline against a real Fuseki
      brought up via this repo's actual `docker-compose.yml` (shiro mount included, no Actions
      `services:` substitute) — SHACL gate, load, all 9 healthcheck invariants,
      `COUNT(:BenchmarkResult) == 88`, and the anon-read/auth-write security posture (anon SELECT
      200, anon GSP write 401). No API key needed; runs parallel to the offline `test` job.
      Verified live locally against real Docker/Fuseki before landing, catching a real bug in the
      process: `scripts/load_data.sh`'s python resolution now verifies a candidate interpreter
      actually runs (not just resolves on PATH) — on this machine `python3` resolves to a
      non-functional Windows Store alias stub, which `command -v` alone would have missed.
- [x] Root-caused a real Fuseki ontology-reload bug (2026-08-06, live diagnostic
      session). Mechanism: POST-to-`/data?default` merges rather than replaces —
      named-URI triples (results, methods, datasets) dedupe correctly under set
      semantics, but blank nodes get a fresh identifier on every parse, so any
      blank-node-rooted axiom (owl:Restriction, owl:AllDisjointClasses, any
      owl:oneOf) duplicates on a repeat ontology load into an already-populated
      store. Isolated empirically in two stages: (1) reloading the DATA file
      (`shwartzziv2022_full.ttl`) twice into the same container left both
      blank-node-rooted triples (41->41) and BenchmarkResult count (88->88)
      unchanged — clean, because ADR-014's deterministic IRIs mean it contains no
      blank nodes; (2) reposting `ontology/mlkg.ttl` alone into that same running
      container exactly doubled blank-node-rooted triples (41->82) and
      owl:Restriction count (5->10), BenchmarkResult count unchanged (88). The
      committed ontology source is clean (5 owl:Restriction, 361 triples total,
      confirmed independently via grep + rdflib against `main`) — this is a
      load-path bug, not data corruption. **Does not affect first-time setup:**
      `make init`/`init_fuseki.sh` always target a fresh empty dataset; only a
      *repeat* ontology load into a populated store triggers it — a
      returning-developer scenario. Not fixed yet; candidates identified: (a) a
      startup guard refusing an ontology load into a non-empty store, same
      fail-loud pattern as the missing-password check; (b) a 10th healthcheck
      invariant asserting owl:Restriction count == 5 post-load. Deferred — see
      Backlog. Side finding: `docs/ONTOLOGY.md`'s stated "289 triples" is stale
      (actual: 361); same class of drift, needs a doc pass alongside the fix.
- [x] Web UI merged (`feature/web-ui` -> `main`, 2026-08-06): a minimal static
      `agent/index.html`, served by the existing FastAPI app at `GET /` — same
      process, same `/ask` route, no separate server or build step (the
      "vanilla JS, no build" approach from the original design). Manually
      tested end-to-end against the live 88-result graph before merging: a
      flagship comparison, a seen/unseen aggregate, and an ambiguous-entity
      question ("the ensemble") all rendered correctly with the right status
      and citation. The answered / refused / ambiguous states get visibly
      distinct styling — an honest "no" is styled calmly, not as an error,
      matching the CLI's own honesty contract at the UI layer.

## Backlog (optional — not a march, pick up if/when the reason applies)
- **Value-scale ADR** — needed only before paper #2 lands: stored-as-printed ×100 factors
  (e.g. cross-entropy) will silently miscompare against an unscaled paper's version of the same
  metric. No urgency while the graph holds one paper.
- **Paper #2** — when there's a real reason to use the tool on a second paper. Will also be the
  first real chance to exercise `multiple_sources` (unreachable with one paper; unit/red-team
  tests cover it until then) and will need a persisted review-decision log (audit H3/ADR-004) —
  "measured, not asserted" reliability currently only holds for paper #1's hand-made gold.
- **Ontology-reload guard + 10th healthcheck invariant** — closes the bug above
  (see Done for full root cause). Low urgency: doesn't affect first-time setup,
  only a repeat ontology load into a populated store. Natural to pick up alongside
  the next real reason to touch the ontology (paper #2, or the value-scale ADR).

## Known behaviors
- The `ambiguous` disambiguation path exists but is rarely reached — the planner resolves vague
  questions by declining (`unsupported`) rather than asking. Safe default; revisit if it matters
  when the corpus grows.

## Known limits
- **CI covers the deterministic half of the pipeline only** — SHACL gate, load, the 9 SPARQL
  invariants, and pure functions. Every LLM-touching path (extraction, the query planner, the
  live eval) is verified manually with a real API key, not in CI. This is the gap that let the
  `temperature` param bug ship undetected (extraction silently sent a param Opus 4.8 rejects)
  until a manual run caught it — CI would not have caught it either, since it can't call the API.
- `multiple_sources` is unreachable with a single-paper graph; covered by unit/red-team tests
  only, not by the live eval or a real query.
- Cross-entropy 100x factor stored as printed (cancels within-table; preserved in caption/metric_raw).
- Paper year (ADR-011 rule) and dataset dedup when a dataset first recurs in a new paper — open
  question, deferred until paper #2 makes it concrete.
- Fuseki ontology reload into an already-populated store duplicates blank-node-rooted
  axioms (owl:Restriction, owl:AllDisjointClasses) — root-caused 2026-08-06, not yet
  fixed. Doesn't affect a first-time clone-and-run; only a repeat ontology load into a
  live store triggers it. Full investigation in Done; fix candidates in Backlog.
