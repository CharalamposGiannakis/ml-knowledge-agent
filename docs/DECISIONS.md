# DECISIONS — Architecture Decision Log

> One short entry per significant decision. Format: what, why, what we rejected.
> A fresh chat reads this to understand *why* the project is the way it is, without re-litigating.

---

### ADR-001 — Knowledge store: RDF/SPARQL (Apache Jena Fuseki)
**Decision.** Use OWL/RDF + SPARQL via Jena Fuseki as the knowledge store.
**Why.** Maximises CV/interview value (SPARQL is rarer and signals more than "I used Postgres")
and serves the goal of learning the semantic-web stack deeply.
**Rejected.** Property graph / Neo4j (simpler, still graph) — would have been faster but lower
learning + CV payoff. Relational + thin semantic layer — too plain for the stated goals.
**Cost accepted.** Higher complexity. Mitigated by the always-working-slice discipline (see ADR-007).

### ADR-002 — Atomic unit is a *result*, not a *comparison*
**Decision.** Store `BenchmarkResult (method, dataset, metric, value, conditions, source)`.
Comparisons are derived at query time.
**Why.** Handles N-way comparison tables natively; faithful to what papers print; lets the agent
compare any two methods sharing conditions, not just author-chosen pairs.
**Rejected.** Comparison-as-atom (per the original README) — combinatorial blowup and information loss.

### ADR-003 — Conditions: required as a concept, partial allowed
**Decision.** Hard-require method, dataset, metric, value, source. Accept-and-flag partial conditions.
**Why.** Real papers are sloppy; a rigid "reject without all conditions" rule rejects most real data.
Flagging lets the agent caveat answers honestly.
**Rejected.** Strict rejection of any result missing conditions (original README stance).

### ADR-004 — Human review is a built feature with logging
**Decision.** Build a small accept/edit/reject UI; persist every decision.
**Why.** Makes "every fact has a source" real; the decision log is a free labeled dataset for
measuring extraction precision. Strong interview talking point.
**Rejected.** Treating review as an informal manual step with no record.

### ADR-005 — Model strategy
**Decision.** Opus 4.8 as default for design-heavy work *and* for runtime extraction. Sonnet for
boilerplate, tests-from-spec, mechanical refactors.
**Why.** Design and extraction are high-leverage and low-volume (tiny corpus, manual review), so
accuracy matters more than per-token cost. Boilerplate doesn't need the strongest model.
**Rejected.** Cheapest model for extraction — false economy given volume is negligible.

### ADR-006 — Reliability is measured, not asserted
**Decision.** Build a ~30-pair eval set early (question → expected source). Report retrieval
precision and citation accuracy.
**Why.** The project's entire pitch is reliability; it must be quantified to be credible.
**Rejected.** Demo-only validation by eyeballing answers.

### ADR-007 — Always-working-slice discipline
**Decision.** At every phase there must be a runnable end-to-end path, even with 1-3 papers.
**Why.** Counterweight to the complexity accepted in ADR-001; protects the "tool I actually use" goal.
**Rejected.** Build-all-infra-then-wire-it-up sequencing (high risk of the empty-cathedral failure).

### ADR-008 — Neo4j as future analytics/exploration layer (parked)
**Decision.** Not adopting Neo4j now. Parked as a documented option for when/if RDF/SPARQL hits bottlenecks.
**Why parked, not rejected.** RDF/OWL handles the semantic layer well for current scope. Neo4j would add
value for graph analytics, citation-path exploration, recommendations, and visualization — but none are
Phase 0-3 concerns. Adding it now violates always-working-slice.
**The division if adopted later:** RDF stays authoritative (ontology, provenance, SHACL); Neo4j becomes a
derived operational/analytical projection. Sync direction RDF -> Neo4j.
**Trigger to revisit.** SPARQL too slow/rigid for navigation, OR corpus large enough that graph analytics pay off.
**Rejected paths.** Neo4j-primary with RDF export (loses semantic guarantees). Dual-primary (no single source of truth).

### ADR-009 — Extraction approach: vision-assisted, JSON intermediate, no auto-commit
**Decision.** Phase 2 extraction = PyMuPDF to render pages + capture page numbers, a **multimodal LLM
(Opus) reading the page image + caption + current ontology vocabulary**, emitting **strict JSON**, which
**code deterministically converts to Turtle** (reusing the Phase-1 emitter), then validates and queues for review.
**Why.** Tables don't survive plain text extraction (multi-column, ±, scientific notation, footnote/brace
markers); a vision model reads them far more faithfully and sees the caption (metric/scaling) in context.
JSON-then-TTL keeps the model out of the business of writing triples, so output is normalizable and validatable.
**Rejected.** Text-only PyMuPDF extraction (mangles real tables); free-form Turtle straight from the LLM
(inconsistent, hard to validate); auto-commit to Fuseki (violates CLAUDE.md rule 1).
**Biggest risk to validate empirically.** Vision-vs-text quality on a real page — test on the Shwartz-Ziv
page where we have gold. Revisit if vision underperforms or cost is prohibitive.

### ADR-010 — The Phase-1 hand-entry is the extraction gold set
**Decision.** Measure Phase 2 extraction by diffing extractor output against `data/shwartzziv2022.ttl`,
reporting per-field precision/recall (value, metric, method/dataset, source).
**Why.** Turns "no hallucination" into a measured number; reuses work already done; directly serves ADR-006.
**Rejected.** Eyeballing extraction quality; building a separate labeled set from scratch.

### ADR-011 — Paper year and date sourcing
**Decision.** Publication year is resolved manually by the human in this order:
DOI (authoritative) → Zotero → arXiv first-submission date. The agent must always
ask for the year rather than inferring it — never auto-populate from paper text,
filename, or model knowledge.
**Why.** Different sources (Google Scholar, Research Rabbit, Zotero) disagree on
dates, especially for preprints with later journal publication. A wrong year
corrupts provenance. Manual lookup via DOI is unambiguous.
**Rejected.** Auto-inferring year from paper content or filename — too error-prone.
Trusting any single secondary source without checking DOI first.

### ADR-012 — Active review: the system raises questions, not lists
**Decision.** The review step is not a passive approval queue. The pipeline classifies every decision
as either high-confidence (auto-proposed, one-keypress approval) or ambiguous (a targeted question,
human answer required before the record can become a triple). No ambiguous decision is resolved silently.
The review UI has two queues: clean records and questions.
**Why.** Passive list-approval fails exactly when the corpus is small and the ontology short — the
human scrolls and rubber-stamps, and a wrong triple slips in. Active review inverts the cognitive load:
unambiguous records flow through instantly; attention is spent only where a real decision exists. This
is the ingestion philosophy made concrete.
**Robustness note (refines the original proposal).** Question-raising is **deterministic and
code-driven**, not based on the LLM's self-reported confidence (which is poorly calibrated). The
guaranteed triggers are rule checks; the LLM may add questions, but it is not the safety net.
**Concrete triggers (machine `reason` codes):** `no_alias_match` (method/dataset/metric string not
among known labels/aliases), `value_parse_mismatch` (parsed value not reproducible from the verbatim
cell), `metric_not_in_vocab` (also needs a direction set), `missing_required`, `caption_metric_unclear`
(table-level), `condition_in_caption` (scope unclear).
**Implementation consequence.** The JSON schema carries a `flags` field. A record with any unresolved
`requires_human_answer` flag is NOT converted to Turtle.
**Rejected.** Passive list approval (too easy to approve without thinking). Full manual entry (too slow,
discards the value of extraction). LLM-confidence as the primary gate (unreliable).

### ADR-013 — Entity identity: raw + canonical, with aliases stored in the graph
**Decision.** Every extracted method, dataset, and metric is captured as a **raw string** plus a
**canonical reference that starts null**. Normalisation maps raw → canonical by matching against the
`rdfs:label` and `skos:altLabel` values already in the graph. A match auto-fills the canonical; a miss
raises `no_alias_match`. On human resolution, the confirmed raw string is added as a `skos:altLabel` on
the chosen canonical individual (so it auto-resolves next time), or a new individual is minted. The
alias "lookup table" therefore **lives inside the RDF graph**, not in a side file.
**Why.** Identity determines whether the system can answer at all — two results compare only if they
point to the same URI, and a silent mis-mapping produces silently incomplete answers. Storing aliases as
`skos:altLabel` keeps a single queryable source of truth, feeds the closed-IE extraction prompt directly
(known labels + aliases are injected into it), and is more semantic-web-idiomatic than a JSON file.
Applying the same mechanism to datasets and metrics (not just methods) closes the same hole everywhere.
**Consequence for metric direction.** `higher_is_better` is NOT stored per result — direction is a
property of the `:Metric` (`:optimizationDirection`). A new metric triggers a one-time human decision on
its direction at review.
**Rejected.** LLM canonicalising during extraction (loses the original, errors invisible until query).
A separate `aliases.json` lookup file (second source of truth, not queryable). Per-record direction flags
(duplicates a fact the graph owns; invites contradiction).

### ADR-014 — Deterministic IRI scheme for pipeline-emitted BenchmarkResults
**Decision.** Change `emit_ttl` to mint IRIs from result identity rather than from raw strings.
Template: `:r_{paper_id}__{method_local}__{dataset_local}__{metric_local}`
where `{X}_local` = local part of the canonical URI, lowercased, non-alnum replaced with `_`.
**Why.** Raw-string slugs (`_slug(method_raw)`) depend on how the model spells the method in a
given run — the same result can produce different IRIs across runs, causing duplicate BenchmarkResult
individuals in Fuseki. Canonical-URI locals are stable: same result → same IRI → idempotent load.
**Future migration.** When conditions become part of result identity the key extends to include a
condition hash (`__{cond_hash}`). This is a deliberate deferred migration; current results have
`conditions_complete: false` so conditions are not yet in the key.
**Gold file.** `data/shwartzziv2022.ttl` (48 hand-reviewed BenchmarkResults, `:r_*` scheme) is
FROZEN as the independent eval gold. It is NOT regenerated from the pipeline.
**Pipeline output.** All pipeline-emitted BenchmarkResults go to `data/{paper_id}_full.ttl` (with
deterministic IRIs), never appended to the gold file.
**Rejected.** Raw-slug URIs (`:prop_*` scheme) — not reproducible across runs. Appending to the
gold file — conflates hand-reviewed and machine-extracted provenance.

### ADR-015 — Reasoning & inference: validate and query, don't materialise
**Decision.** The asserted graph holds **only paper-sourced triples**. We do NOT materialise
OWL/RDFS-inferred triples into it, and we do not run inference during structural validation.
Enforcement is two-layered: (1) **SHACL as a pre-load gate**, run with `inference="none"` so
`sh:class` checks see **asserted types only**; (2) a **SPARQL invariant pack run post-load**
against Fuseki, covering both referential/uniqueness checks (metric-has-direction, no dangling
method, no duplicate results) and the logical checks that a reasoner would otherwise be asked for
(disjoint-class cross-typing, functional-property multi-values). Derived facts we want at query
time (e.g. method-family closure) are obtained via **SPARQL property paths**
(`:inFamily/:subFamilyOf*`), not stored.
**Why.** Provenance is the core invariant — every stored triple must trace to a paper. Inferred
triples have no paper source; mixing them into the asserted graph blurs "a paper said X" vs "a
reasoner derived X" and breaks the agent's no-source-no-claim guarantee. SPARQL paths give the
hierarchy convenience without storage. SHACL gives the closed-world rejection OWL's open-world
semantics cannot — but only if inference is off; RDFS closure over `rdfs:range` (e.g. `:onDataset
rdfs:range :Dataset`) infers every object of `:onDataset` as a `:Dataset` regardless of its real
type, making `sh:class` checks vacuous.
**Revised (this audit): the OWL-reasoner layer is gone, not just transient.** The original
decision ran `owlrl`'s OWL RL closure transiently for a periodic consistency check
(`scripts/consistency.py`), on the theory that it would catch disjoint-class and
functional-property violations SHACL doesn't reach. Verified empirically: it did not. Run against
a graph with an individual typed both `:Method` and `:Dataset`, and against a `BenchmarkResult`
carrying two different `:hasValue` literals, `owlrl`'s closure printed `CONSISTENT` for both —
`owl:AllDisjointClasses` and `owl:FunctionalProperty` violations do not manifest as `owl:Nothing`
membership under RL semantics the way the original design assumed. Keeping a check that reports
"consistent" over broken states is worse than no check. `scripts/consistency.py` and the `owlrl`
dependency are removed; the violations it was meant to catch are now plain SPARQL `SELECT` queries
(checks E-H in `docs/health_checks.md`) run in the same post-load pass as the other invariants.
**If materialised inference is ever needed** (performance), it goes in a SEPARATE named graph
(`:inferred`), never the default/asserted graph, so the agent can include or exclude it explicitly.
**Rejected.** Always-on Fuseki inference model over the base graph (pollutes provenance, premature
at this scale). Relying on OWL cardinality restrictions for enforcement (open-world; documents but
never rejects). Storing reasoner output alongside asserted facts. Keeping the OWL reasoner layer
for the checks it silently failed to perform.

**Test layers in force:** (1) SHACL pre-load gate (inference off), (2) SPARQL invariant pack
post-load (referential integrity + logical invariants, formerly split as "Layer 2"/"Layer 3"),
(3) eval set (ADR-006). See `docs/health_checks.md`.

### ADR-016 — Proportionate strictness: minimal enforced invariants, permissive elsewhere, tighten only on demonstrated failure
**Decision.** Strictness is added only where a real invariant of the project's promise lives, and
only after a concrete failure demonstrates the need. Everything else stays permissive and evolvable.
Two instances in force:
1. **Schema / validation.** The *enforced* set is minimal and load-bearing: every BenchmarkResult
   has a source, references resolve to asserted types, every Metric has a direction, the required
   core is present, IRIs are unique (SHACL pre-load gate + SPARQL invariants, ADR-015). Everything
   beyond that — OWL disjointness/cardinality axioms, controlled vocabularies, the reified
   condition apparatus (num/text/min/max/ConditionType) — is documentation and future capacity,
   not a gate. Constraints are not added speculatively; one earns its place only when a real paper
   produces a real failure, captured as an adversarial fixture (like the three in `tests/`) before
   the shape/invariant is tightened.
2. **Store access.** Fuseki runs read-open, write-gated: anonymous SPARQL SELECT (`/*/query`,
   `/*/sparql`), authenticated writes/admin. This is least-privilege aimed at the component that
   will carry risk — the future read-only query agent must never hold write credentials, so a
   prompt-injected or buggy agent cannot be steered into a SPARQL UPDATE. The trigger to add a
   read credential is a demonstrated one: exposure of the store beyond localhost.
**Why.** The audit (`docs/fable.md`) exposed the failure mode this prevents: elaborate strictness
that enforced nothing (owlrl caught no violations; OWL cardinality restrictions were open-world
documentation) next to a gate that passed dangling references — over-specified in schema,
under-enforced at the gate, the worst of both. The image-pin incident showed the same reflex
operationally: locking down reads "to be safe" broke a working system against a threat that did
not exist. Proportionate strictness is the corrective: enforce the promise, stay loose elsewhere,
and let demonstrated failures — a red fixture, an actual exposure — earn each new constraint. A
permissive schema is safe to evolve precisely because the load-bearing gate now holds (ADR-015).
**Consequence for open work.** Where earlier ADRs imply broad up-front strictness, this is the
governing meta-rule: they bind for the minimal enforced set and are advisory beyond it. The
condition model (next task) is built to the minimal shape that makes IRIs unique and lets the
agent caveat — not the full apparatus — until a real query proves more is needed.
**Rejected.** Strict-everywhere-up-front (constraints for papers/threats not yet met; brittle, slow,
often illusory). Relax-everything (unsafe without the minimal gate). Read-authenticated access
(puts write credentials in the read-only agent's hands; inverts the threat model).

### ADR-017 — Seen/unseen is a derived annotation, not an identity-bearing condition; IRI slug deferred
**Decision.** (1) Model the paper's seen/unseen variable as a lightweight annotation on
BenchmarkResult (`:datasetSeenByModel` in {"seen","unseen"}), applied to the four deep models
per Table 1's provenance; omitted for XGBoost and the ensembles (no originating paper → N/A).
(2) Seen/unseen does NOT enter the IRI and is NOT a joinable `:Condition`. (3) The IRI
condition-slug migration is deferred to the first paper reporting one (method,dataset,metric)
under multiple genuine experimental conditions (paper #2: label-noise levels), and applied to
that paper's results — not retrofitted onto the current 88.
**Why.** Seen/unseen is functionally determined by (model,dataset): a pair is seen or unseen,
never both, so it never splits a (method,dataset,metric) into two results and cannot collide —
the current 88 IRIs are already unique and need no migration (this revises audit H4 / the STATUS
next-action, which assumed a collision that cannot occur). It is also model-specific, not shared
setup: as a joinable `:Condition` it would break the paper's central comparison (XGBoost, which
has no seen/unseen status, vs a deep model that does). An annotation keeps it queryable without
breaking joins and reserves the reified `:Condition` machinery for a real shared condition
(paper #2's noise). Deferring the slug follows ADR-016 — build on demonstrated need — and costs
nothing extra, since the 88 are never re-IRI'd either way.
**Rejected.** Seen/unseen in the IRI (encodes a derived fact; churns 88 IRIs for no benefit).
Seen/unseen as a joinable `:Condition` (breaks XGBoost-vs-deep comparison). A condition-hash
migration "now" (fixes a non-existent collision). Flat boolean (loses the N/A case for baselines).

### ADR-018 — Query trust boundary: the agent selects operations, it does not write SPARQL
**Decision.** The query agent translates a natural-language question into a CHOICE among a small
library of hand-written, tested, parameterised SPARQL operations (compare, rank, lookup,
filter-aggregate, provenance). The LLM resolves entities to canonical URIs (matching the question's
terms against rdfs:label / skos:altLabel already in the graph), selects the operation, fills its
slots, and narrates the returned rows with their sources. The LLM never emits raw SPARQL.
Deterministic code owns the query language — exactly as ADR-009 has code, not the model, own
triple-writing on ingestion.
**Why.** The project's guarantee is sourced, non-fabricated answers. An LLM writing free SPARQL can
produce fluent, cited, semantically-wrong answers (wrong join, wrong condition filter, inverted
metric direction, incommensurable-scale comparison) — reintroducing hallucination at the query
layer, the exact failure the structured graph exists to prevent. Fixed operations are verified once
and tested; metric direction is read from :optimizationDirection, never guessed. Benchmark questions
are structurally bounded (compare/rank/lookup/filter/provenance), so a small operation set covers
most real questions; an unsupported shape yields an honest "I can't express that yet", preferable to
a confident wrong answer. Operations are added only when a real question demands one (ADR-016).
**Consequences.** Entity resolution reuses the SKOS alias infrastructure from ADR-013. The agent
holds read-only credentials (ADR-016), so no query can mutate the graph. Narration is constrained to
returned rows + their SourceLocations; the agent adds no facts.
**Errata (ADR-019).** "narrates the returned rows" originally meant *free-form LLM prose behind a
token-provenance guard*. The red-team (`docs/redteam.md` F1) showed that guard is truth-blind;
ADR-019 supersedes the narration half of this ADR — the asserted answer is now rendered
deterministically by code, and the LLM never writes the answer sentence.
**Rejected.** Text-to-SPARQL (LLM writes the query) — violates the ADR-009 boundary on the query
side; schema-validation can't catch semantic errors. Text-to-SPARQL-with-validation-gate — PARKED as
a documented future option (cf. ADR-008) for when the operation library demonstrably can't express a
needed question; not built pre-emptively. Bare templates without entity resolution — brittle on
naming variants.

### ADR-019 — The model interprets; code asserts. Narration is deterministic.
**Decision.** The query agent's answer text is rendered deterministically by code from a
structured, verified payload (winner, per-entity values, optimization direction, citation). The
LLM is confined to interpretation — resolving entities, selecting the operation, filling slots
(all language-in tasks). It does NOT write the asserted content of the answer. Free-form LLM
narration is removed from the default answer path (retained, if at all, only behind an explicit
non-default flag, and the untrusted question is never placed in a narrator prompt). The narration
guard is kept as defense-in-depth, not as the primary guarantee.
**Why.** The red-team (`docs/redteam.md`, F1) showed the token-provenance guard is truth-blind:
real numbers + a real citation + real methods compose into false sentences that pass, and metadata
digits (locator, page, year) leak into the allowed-value set; the untrusted question reaches the
narrator prompt, a direct injection path. Provenance of tokens is not truth of the sentence, and a
smarter guard is an unwinnable arms race against natural language. The principled fix is the
symmetry already applied to data (ADR-009) and queries (ADR-018): the model never writes the formal
artifact. Extending it to the answer sentence closes the seam by construction and removes the
injection path (the question no longer influences answer wording).
**Consequences.** Answers are structured objects rendered to prose by code; the eval scores the
rendered answer claim-locally (revises ADR-006's harness). Shapers must produce correct, honest
payloads (red-team F2/F3/F4). At four operations, four templates suffice; revisit only if the
operation library grows large (ADR-016).
**Rejected.** Guard-as-truth-checker (unbounded NL attack surface; F1's permutations are the tip).
Keeping free LLM narration as default behind a better guard (same arms race).