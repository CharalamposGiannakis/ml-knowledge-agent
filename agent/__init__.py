"""MLKG query agent — natural-language question -> sourced answer (ADR-018).

The LLM never writes SPARQL. It resolves question terms to canonical URIs
(against rdfs:label / skos:altLabel in the graph), selects one hand-written
parameterised operation, fills its slots, and narrates the returned rows.
Deterministic code owns the query language, winner logic (via
:optimizationDirection), and the guard on narration.
"""

from agent.loop import Answer, answer_question

__all__ = ["Answer", "answer_question"]
