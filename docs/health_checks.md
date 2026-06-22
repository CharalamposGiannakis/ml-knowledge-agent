# Ontology / graph health checks

Four layers. Run layers 1-2 on every paper add; layer 3 when the ontology changes
or periodically; layer 4 is the existing eval set.

## Layer 1 — SHACL (PRE-LOAD GATE, structural)
Validate the candidate `.ttl` against `ontology/shapes.ttl` (pyshacl). If it does not
conform, DO NOT load. Enforces: required core (method/dataset/metric/value/source),
referential integrity (sh:class), every Metric has a direction, conditionsComplete present.

## Layer 2 — SPARQL invariants (POST-LOAD, run against Fuseki)
Each query must return ZERO rows unless noted. Non-empty = FAIL.

```sparql
# A. metrics missing a direction  (expect 0)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?m WHERE { ?m a :Metric . FILTER NOT EXISTS { ?m :optimizationDirection ?d } }
```
```sparql
# B. results pointing at an undefined method  (expect 0)
PREFIX : <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?r WHERE { ?r a :BenchmarkResult ; :reportsMethod ?m .
  FILTER NOT EXISTS { ?m rdfs:label ?l } }
```
```sparql
# C. duplicate results — same method+dataset+metric, different IRI  (expect 0; guards ADR-014)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?a ?b WHERE {
  ?a a :BenchmarkResult ; :reportsMethod ?m ; :onDataset ?d ; :usesMetric ?me .
  ?b a :BenchmarkResult ; :reportsMethod ?m ; :onDataset ?d ; :usesMetric ?me .
  FILTER(STR(?a) < STR(?b)) }
```
```sparql
# D. flagship regression — must return 80.64  (expect 1 row)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?v WHERE { ?r :reportsMethod :XGBoost ; :onDataset :ds_gesture ;
  :usesMetric :CrossEntropyLoss ; :hasValue ?v }
```
```sparql
# E. (sanity, not a gate) family closure WITHOUT a reasoner, via property path
PREFIX : <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label WHERE { ?m :inFamily/:subFamilyOf* :TreeEnsemble ; rdfs:label ?label }
```

## Layer 3 — OWL consistency (PERIODIC, transient — DO NOT MATERIALIZE)
Run an OWL reasoner over ontology+data; assert the model is consistent; discard the
inferred graph. Catches disjoint-class violations, functional-property contradictions.
Never write inferred triples into the asserted graph (ADR-015).

## Layer 4 — Eval set (semantic)
`eval/eval_set.jsonl` Q -> expected source. Retrieval + citation accuracy (ADR-006).
