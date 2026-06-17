# Extraction Pipeline — Design Constraints (Phase 2)

Findings from pre-implementation research. These constrain prompt and pipeline design choices.

1. **Use RAG few-shot, not CoT/ReAct/Self-Consistency.** RAG few-shot retrieval outperforms chain-of-thought and multi-step reasoning strategies for structured triple extraction from ML papers.

2. **One retrieved example beats many canonical ones.** A single high-quality example retrieved for the specific input context outperforms providing multiple generic canonical examples; prefer dynamic retrieval over a fixed few-shot bank.

3. **Embed the ontology schema explicitly in every extraction prompt.** Closed IE requires the model to see the exact class/property names from `ontology/mlkg.ttl` at prompt time; without it, LLMs invent ad-hoc predicates that break the schema.

4. **Post-processing must handle inconsistent triple formats.** LLMs return triples in varying surface forms (JSON, Turtle fragments, prose, mixed quoting); the pipeline must normalize all outputs to valid Turtle before any validation or review step.

5. **Never auto-commit extracted triples.** All extraction output goes to a human-review queue; no triple reaches Fuseki without explicit approval (see CLAUDE.md rule 1).

6. **Required fields gate acceptance, not rejection.** If method/dataset/metric/value/source are all present, accept. Partial triples are flagged for review, not silently dropped (see CLAUDE.md rule 5).
