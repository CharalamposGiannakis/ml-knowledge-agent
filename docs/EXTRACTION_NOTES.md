# EXTRACTION_NOTES — Phase 2 Plan & Design Constraints

> Phase 2 turns a paper PDF into *proposed, validated* triples for human review.
> This file is the living plan. The pre-implementation research findings (bottom) still
> constrain prompt/pipeline design; the plan above them is what we'll actually build.

---

## Status & build-gate
**Planning only.** Phase 2 *coding* is gated on the live end-to-end slice being confirmed
(Phase 0/1 answering a real query against a running Fuseki). Planning now is cheap and
reversible; building the pipeline before the slice is live would violate ADR-007.

## Goal (one sentence)
PDF → a set of proposed `BenchmarkResult` records, normalized to the ontology, validated, and
written to a review queue. **Never auto-committed to Fuseki** (CLAUDE.md rule 1).

## Scope of v1 (deliberately narrow — resist creep)
- **In:** one results table per run → proposed triples for the required core
  (method, dataset, metric, value) + stdError + source (locator, page).
- **Out (later):** extracting *conditions* from prose; the review UI (Phase 3); auto-loading to
  Fuseki; whole-paper multi-table ingestion. v1 results enter flagged `:conditionsComplete false`.

## Pipeline stages
1. **Locate & render (PyMuPDF).** Split PDF to pages; capture the page number (provenance);
   render the target page to an image; optionally use table-finding to locate the table region
   and its caption.
2. **Extract (multimodal LLM, Opus).** Feed the *page image* + the *caption* + the *current
   ontology vocabulary*. Closed IE. Output **strict JSON records**, not free-form Turtle.
3. **Normalize & link.** Map method/dataset/metric strings to existing individuals; mark unknowns
   as `proposed-new` for the reviewer. (Fuzzy linking via ChromaDB embeddings is an option here.)
4. **Emit TTL (deterministic).** JSON → Turtle using the same emitter pattern already written for
   the Shwartz-Ziv hand-entry. The model proposes data; code (not the model) writes the triples.
5. **Validate (the gate).** rdflib parse + required-core present + numeric types + metric/method
   resolve-or-flagged. (SHACL can slot in here; a Python validator is enough for v1.)
6. **Queue for review.** Write `proposals/<paper>.jsonl` + a human-readable summary, then **stop.**

## The big difficulties (this is where the project lives or dies — track these, not minutiae)
1. **Tables don't survive plain text extraction.** Multi-column layout, merged cells, ± symbols,
   scientific notation (`55.43±2e-2`), footnote markers, brace/grouping annotations — PyMuPDF's
   raw text mangles these. → the text-vs-vision fork; see ADR-009. Recommendation: vision.
2. **Conditions don't live in the table.** The 100× factor was in the *caption*; seen/unseen was
   in *prose*; dataset sizes were in a *different table*. Faithful condition capture means reading
   beyond the results table. → v1 scopes conditions OUT and flags `:conditionsComplete false`.
3. **Metric is not uniform within a table.** Shwartz-Ziv Table 2: MSE for two columns,
   scaled cross-entropy for the rest — defined only in the caption. → always feed caption +
   column headers + row headers + cell together; never extract a bare cell.
4. **Normalization / entity-linking & dedup.** "CoverType" vs "Forest Cover Type", "1D-CNN" vs
   ":OneDCNN", per-paper dataset variants (different size/split). → put current vocabulary in the
   prompt; reuse-or-propose; revisit shared dataset reference when a dataset first recurs.
5. **Output discipline.** LLMs emit triples in inconsistent surface forms. → constrain to strict
   JSON, convert to TTL deterministically in code. (Refines research finding #4.)

## Measuring it (ties Phase 2 to ADR-006)
Run the extractor on the Shwartz-Ziv page and **diff against `data/shwartzziv2022.ttl`** (the
hand-reviewed gold). Report per-field precision/recall: did it get the right value, the right
metric, the right method/dataset, the right source? This is the headline interview number.

## What's left / open questions
- [ ] Verify PyMuPDF in the env supports page rendering + table-finding.
- [ ] Confirm current Anthropic API limits for page-image / PDF input (check docs.claude.com).
- [ ] Define the JSON record schema (fields: method, dataset, metric, value, stdError, locator,
      page, raw_cell_text, proposed_new flags).
- [ ] Normalization strategy: exact-match + LLM-proposed first; add embedding similarity only if needed.
- [ ] Empirically test vision-vs-text extraction quality on the Shwartz-Ziv page (gold available).
- [ ] Define the precision/recall scoring script for the gold diff.

---

## Pre-implementation research findings (still in force)

1. **RAG few-shot, not CoT/ReAct/Self-Consistency** for structured triple extraction. With vision,
   the retrieved example becomes an (page-image → correct-JSON) pair.
2. **One retrieved example beats many canonical ones** — prefer dynamic retrieval of the single
   most relevant example over a fixed bank.
3. **Embed the ontology schema explicitly in every extraction prompt** (closed IE) — the model must
   see the exact class/property/individual names from `ontology/mlkg.ttl`, or it invents predicates.
4. **Post-processing must normalize inconsistent outputs** — enforced here by the strict-JSON →
   deterministic-TTL decision (ADR-009).
5. **Never auto-commit** — all output goes to the review queue (CLAUDE.md rule 1).
6. **Required fields gate acceptance, not rejection** — core present ⇒ accept; partial conditions ⇒
   flag, don't drop (ADR-003).
