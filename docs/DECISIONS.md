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
