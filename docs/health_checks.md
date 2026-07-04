# Ontology / graph health checks

Three layers. Run layers 1-2 on every paper add; layer 3 is the existing eval set.

## Layer 1 — SHACL (PRE-LOAD GATE, structural)
Validate the candidate `.ttl` against `ontology/shapes.ttl` (pyshacl), with **inference
disabled** (`inference="none"`). If it does not conform, DO NOT load. Enforces: required
core (method/dataset/metric/value/source), referential integrity via **asserted types**
(sh:class — every entity must already be typed :Method/:Dataset/:Metric/etc., not
inferred), rdfs:label present on Method/Dataset (catches dangling/typo'd URIs), every
Metric has a direction, conditionsComplete present.

**Why inference is off.** RDFS closure over `rdfs:range` (e.g. `:onDataset rdfs:range
:Dataset`) infers every object of `:onDataset` as a `:Dataset` regardless of its real
type — this makes `sh:class` checks vacuous (a `:Method` plugged into `:onDataset`
would silently pass). Our entities are explicitly typed, so asserted-type checking is
what we want.

## Layer 2 — SPARQL invariants (POST-LOAD, run against Fuseki)
Also includes the logical invariants that used to be labelled "Layer 3" (see below) —
cross-typing and multi-value checks now live here as ordinary post-load SPARQL, run by
`scripts/healthcheck.py`.
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
# E. individuals cross-typed Method/Dataset  (expect 0; disjoint-class guard)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?x WHERE { ?x a :Method, :Dataset }
```
```sparql
# F. individuals cross-typed Method/Metric  (expect 0; disjoint-class guard)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?x WHERE { ?x a :Method, :Metric }
```
```sparql
# G. individuals cross-typed Dataset/Metric  (expect 0; disjoint-class guard)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?x WHERE { ?x a :Dataset, :Metric }
```
```sparql
# H. BenchmarkResults with two different :hasValue literals  (expect 0; functional-property guard)
PREFIX : <http://mlkg.local/ontology#>
SELECT ?r WHERE { ?r :hasValue ?v1 ; :hasValue ?v2 . FILTER(?v1 != ?v2) }
```
```sparql
# I. (sanity, not a gate) family closure WITHOUT a reasoner, via property path
PREFIX : <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label WHERE { ?m :inFamily/:subFamilyOf* :TreeEnsemble ; rdfs:label ?label }
```

**On the retired OWL-reasoner layer.** An earlier version of this harness ran `owlrl`'s
OWL RL closure transiently (`scripts/consistency.py`) to catch disjoint-class and
functional-property violations. Verified during the ADR-015 audit: it did **not** catch
either — it printed `CONSISTENT` over graphs with a cross-typed individual and over a
`BenchmarkResult` with two different `:hasValue` literals. `owlrl` has been removed as a
dependency; checks E-H above are the direct replacement, expressed as plain SPARQL
invariants rather than reasoner output.

## Layer 3 — Eval set (semantic)
`eval/eval_set.jsonl` Q -> expected source. Retrieval + citation accuracy (ADR-006).
