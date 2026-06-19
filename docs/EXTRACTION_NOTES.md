# EXTRACTION_NOTES — Phase 2 Plan & Design Constraints

> Phase 2 turns a paper PDF into *proposed, validated* triples for human review.
> This file is the living plan. The pre-implementation research findings (bottom) still
> constrain prompt/pipeline design; the plan above them is what we'll actually build.

---

## Status & build-gate
**Gate cleared.** Phase 0/1 live slice confirmed (Fuseki up, 48 results loaded, flagship
comparison query passing). JSON schema finalised. Phase 2 implementation can begin.

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

---

## The JSON contract (v1) — finalised

The JSON is the handoff between the vision LLM (produces it) and deterministic Python (reads it,
writes Turtle). The LLM only has to get the JSON right; all RDF complexity lives in code.

```jsonc
{
  "schema_version": "1.0",
  "paper_id": "shwartzziv2022",          // key only; paper metadata lives separately (Decision 3)
  "extracted_by": "claude-opus-4-8",      // reproducibility / provenance
  "source": {
    "locator": "Table 2",
    "page": 6,
    "caption": "Test results on tabular datasets ... (lower value is better)"
  },
  "table_flags": [],                       // table-level questions, e.g. caption_metric_unclear
  "results": [
    {
      "method_raw":     "Deep Ensemble w/ XGBoost (Shwartz-Ziv)",
      "method_canonical": null,            // filled by normalisation or review (ADR-013)
      "dataset_raw":    "Gesture",
      "dataset_canonical": null,
      "metric_raw":     "Cross-entropy loss (x100)",
      "metric_canonical": null,
      "value":     78.93,
      "std_error": 0.73,
      "raw_cell":  "78.93 ± 0.73",         // verbatim → enables re-parse check; becomes :sourceText
      "conditions": [                       // typed list (Decision 2); often empty in v1
        // {"type": "split", "value_text": "seen", "value_num": null, "unit": null}
      ],
      "conditions_complete": false,         // ADR-003
      "flags": [
        {
          "field": "method_canonical",
          "reason": "no_alias_match",
          "question": "‘Deep Ensemble w/ XGBoost (Shwartz-Ziv)’ matched no known method. New method, or alias/variant of an existing one?",
          "options": ["new_method", "alias_of:<uri>", "variant_of:<uri>"],
          "requires_human_answer": true
        }
      ]
    }
  ]
}
```

**Key rules**
- `*_canonical` is `null` until resolved. `higher_is_better` is **not** a field — direction is on the
  `:Metric` in the graph (ADR-013).
- A result with any unresolved `requires_human_answer: true` flag is **not** converted to Turtle (ADR-012).
- `value` + `std_error` are stored as printed; `raw_cell` lets code re-parse and verify them
  (mismatch → `value_parse_mismatch` flag). Metric scaling (e.g. ×100) stays visible in `metric_raw`
  and `source.caption`; it is a known cross-paper risk, not a per-record field.

## Normalisation & flag loop (deterministic)

1. **Before extraction:** SPARQL the live graph for every `:Method` / `:Dataset` / `:Metric` with its
   `rdfs:label` and `skos:altLabel`. Inject this vocabulary into the extraction prompt (closed IE).
2. **After extraction:** for each `*_raw`, code matches (normalised: trim/casefold) against labels +
   altLabels. Hit → fill `*_canonical`. Miss → raise `no_alias_match`. Also run `value_parse_mismatch`,
   `metric_not_in_vocab`, `missing_required` checks.
3. **At review:** human answers each question. A confirmed alias is written back as `skos:altLabel` on
   the canonical individual (auto-resolves next time); a genuinely new entity is minted. Only then does
   the clean record convert to TTL and load.

> Ontology touch needed: add `@prefix skos:` and use `skos:prefLabel`/`skos:altLabel` on the canonical
> Method/Dataset/Metric individuals. Small, additive — hand to Claude Code.

## What's left (current)
- [x] JSON schema finalised (this section). ADR-012, ADR-013 logged.
- [x] Normalisation strategy decided: exact-match against `rdfs:label`/`skos:altLabel`; propose-new on miss.
- [ ] Add `skos:` prefix + `skos:prefLabel`/`skos:altLabel` to `ontology/mlkg.ttl` (additive, pre-coding).
- [ ] Confirm PyMuPDF page rendering + `find_tables` in the env.
- [ ] Confirm Anthropic API page-image limits.
- [ ] Build the first vertical cut: render page → vision call → JSON → normalise-against-graph →
      TTL emit → validate → write `proposals/<paper>.jsonl` + flag queue. No auto-commit.
- [ ] Run extractor on the Shwartz-Ziv page; diff vs `data/shwartzziv2022.ttl` gold; report per-field
      precision/recall (value, metric, method/dataset, source).

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
