# ONTOLOGY — ML Engineering Knowledge Graph

> Documentation for `ontology/mlkg.ttl` (the canonical, loadable schema).
> The `.ttl` is the source of truth for the schema; this file explains *why* it is shaped that way.
> Namespace: `http://mlkg.local/ontology#` (prefix `:`).
> Status: validated — parses to 289 triples; the flagship comparison query runs (see below).

---

## The shape in one paragraph

Everything hangs off **`:BenchmarkResult`** — one method's measured value, on one dataset, by one
metric, under zero-or-more conditions, with exactly one source location. The four core links
(`:reportsMethod`, `:onDataset`, `:usesMetric`, `:hasSource`) plus `:hasValue` are
`owl:FunctionalProperty` — a result has exactly one of each. Conditions are reified
(`:Condition` nodes) so they can be queried and range-filtered. A **comparison is never stored**;
it is a SPARQL pattern that joins two results sharing dataset + metric + condition and diffs them.

---

## Class map

| Class | Role |
|---|---|
| `:BenchmarkResult` | **The atom.** method + dataset + metric + value + conditions + source. |
| `:Method` / `:MethodFamily` | An algorithm and its (nestable) family. |
| `:Dataset` | A dataset or dataset variant; intrinsic descriptors (`:numRows`, `:numFeatures`, `:datasetDomain`). |
| `:Metric` | An evaluation metric, carrying `:optimizationDirection`. |
| `:Condition` / `:ConditionType` | A reified experimental condition + its controlled-vocabulary type. |
| `:SourceLocation` | Where in a paper the result lives (`:locator`, `:page`, optional `:sourceText`). |
| `:Paper` | Publication metadata. |
| `:OptimizationDirection` | Enumerated `:HigherIsBetter` / `:LowerIsBetter`. |

Top-level domain classes are declared pairwise disjoint (`owl:AllDisjointClasses`).

---

## Five deliberate refinements beyond the DESIGN.md sketch

These are upgrades over the original sketch; each earns its place.

1. **Metric direction (`:optimizationDirection`).** The sketch could store values but couldn't say
   *who won* — F1 is higher-is-better, latency is lower-is-better. Without direction, a derived
   comparison can't name a winner. Now it can.
2. **Numeric vs text condition values.** Split into `:conditionValueNum` (+ optional
   `:conditionValueMin`/`Max`, `:conditionUnit`) and `:conditionValueText`. This is what makes the
   README's *"around 5,000 rows"* / *"noisy labels"* query executable as numeric `FILTER`s rather
   than string matching.
3. **Condition types as a controlled vocabulary.** `:ConditionType` individuals (`:LabelNoise`,
   `:NumRowsCond`, `:ClassImbalance`, …) resolve the STATUS open question: **predefine a small set,
   add individuals as new types emerge.** Prevents `"label_noise"` vs `"labelNoise"` drift.
4. **Functional core + cardinality restrictions.** The five required-core fields (ADR-003) are
   marked functional and carry `owl:cardinality 1` restrictions on `:BenchmarkResult` — the schema
   now *documents* the hard requirement.
5. **`:conditionsComplete` flag + light ingestion provenance.** Encodes ADR-003's accept-and-flag:
   a result with partial conditions enters with `:conditionsComplete false`, and the agent must
   caveat. `:extractedBy` / `:reviewedon` record how a triple got into the graph.

---

## Example: one result set (this is *data*, not schema)

Schema and controlled vocabulary live in the `.ttl`. **Paper-derived data never does** — it enters
only after human review. A hand-entered Phase-1 paper looks like:

```turtle
:r_rf a :BenchmarkResult ;
    :reportsMethod :RandomForest ; :onDataset :ds_noisy ; :usesMetric :F1 ;
    :hasValue 0.812 ; :underCondition :c_noise ; :hasSource :src_t3 ; :conditionsComplete true .
:c_noise a :Condition ; :conditionType :LabelNoise ; :conditionValueNum 30 ; :conditionUnit "%" .
:src_t3  a :SourceLocation ; :fromPaper :paper_smith2022 ; :locator "Table 3" ; :page 8 .
```

## The flagship query (validated, runs against the example above)

```sparql
PREFIX :    <http://mlkg.local/ontology#>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
SELECT ?mA ?vA ?mB ?vB ?noise ?locator ?page WHERE {
  ?rA :reportsMethod ?methA ; :onDataset ?d ; :usesMetric :F1 ; :hasValue ?vA ;
      :underCondition ?cond ; :hasSource ?s .
  ?rB :reportsMethod ?methB ; :onDataset ?d ; :usesMetric :F1 ; :hasValue ?vB .
  ?cond :conditionType :LabelNoise ; :conditionValueNum ?noise .
  ?d :numRows ?n . ?s :locator ?locator ; :page ?page .
  ?methA rdfs:label ?mA . ?methB rdfs:label ?mB .
  FILTER(?methA != ?methB && ?vA > ?vB)     # ?mA is the winner (F1 = higher-is-better)
  FILTER(?n >= 4000 && ?n <= 6000)           # "around 5,000 rows"
  FILTER(?noise >= 15)                        # "noisy labels"
}
```
Returns: *Random Forest beat XGBoost on F1 by +0.023 (noise=30%, n~5000) — Table 3, p.8.*
The winner direction (`?vA > ?vB`) should be flipped to `<` when the metric is lower-is-better;
the agent reads `:optimizationDirection` to decide which.

---

## Known modelling tension (documented, not yet resolved)

**Dataset characteristics vs conditions overlap.** `:numRows` can live on `:Dataset` *or* as a
`:NumRowsCond` condition. Rule of thumb in force: intrinsic/stable descriptors → `Dataset`;
knobs that vary across results in the same paper (injected noise, subsampled rows, feature subset)
→ `Condition`. Revisit if it causes duplicate-match headaches.

---

## What's intentionally deferred

- **Standard-vocabulary alignment.** A mature version maps `:title`→`dcterms:title`,
  `:hasSource`→`prov:wasDerivedFrom`, papers→BIBO. Kept in our own namespace for now for clarity;
  align after Phase 1 so it doesn't slow the first working slice.

## SHACL enforcement (enforced as pre-load gate — `ontology/shapes.ttl`)

SHACL is now enforced as a pre-load gate via `scripts/validate_shapes.py`. The OWL cardinality
restrictions *document* the required core; `ontology/shapes.ttl` *rejects* any conformance failure
before a .ttl reaches Fuseki. The shapes cover: required core (method/dataset/metric/value/source),
referential integrity (`sh:class`), metric direction, conditionsComplete flag, SourceLocation fields,
and Paper fields. See `docs/health_checks.md` for the full four-layer test strategy (ADR-015).
