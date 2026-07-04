"""Entity catalog: every Method / Dataset / Metric in the graph with its
rdfs:label and skos:altLabel values (ADR-013 alias infrastructure).

The catalog is the trust boundary's membership list: the planner LLM may only
fill operation slots with URIs that appear here, and the loop verifies that
membership (plus entity type) before any SPARQL is built.

Mirrors the vocabulary query in scripts/phase2_extract.py:fetch_vocabulary,
which serves the same role on the ingestion side.
"""
from dataclasses import dataclass, field

ONTO_NS = "http://mlkg.local/ontology#"

CATALOG_QUERY = """
PREFIX :     <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?uri ?label ?altLabel ?type WHERE {
  VALUES ?type { :Method :Dataset :Metric }
  ?uri a ?type ; rdfs:label ?label .
  OPTIONAL { ?uri skos:altLabel ?altLabel }
}
ORDER BY ?type ?label
"""


def short(uri: str) -> str:
    """':XGBoost' form for display."""
    return ":" + uri.replace(ONTO_NS, "") if uri.startswith(ONTO_NS) else uri


@dataclass
class Entity:
    uri: str
    label: str
    type: str  # "Method" | "Dataset" | "Metric"
    aliases: list = field(default_factory=list)


class Catalog:
    def __init__(self, entities: dict):
        self.entities = entities  # uri -> Entity

    @classmethod
    def fetch(cls, backend) -> "Catalog":
        entities: dict = {}
        for row in backend.select(CATALOG_QUERY):
            uri = row["uri"]
            e = entities.get(uri)
            if e is None:
                e = Entity(
                    uri=uri,
                    label=row["label"],
                    type=row["type"].replace(ONTO_NS, ""),
                )
                entities[uri] = e
            alt = row.get("altLabel")
            if alt and alt not in e.aliases and alt != e.label:
                e.aliases.append(alt)
        return cls(entities)

    def get(self, uri: str):
        return self.entities.get(uri)

    def find(self, term: str) -> list:
        """Deterministic exact (casefolded) match against labels and aliases."""
        t = term.strip().casefold()
        return [
            e for e in self.entities.values()
            if e.label.casefold() == t or any(a.casefold() == t for a in e.aliases)
        ]

    def prompt_block(self) -> str:
        """Catalog rendered for the planner prompt: URI — label (aliases)."""
        by_type: dict = {}
        for e in self.entities.values():
            by_type.setdefault(e.type, []).append(e)
        lines = []
        for t in ("Method", "Dataset", "Metric"):
            lines.append(f"{t}s:")
            for e in sorted(by_type.get(t, []), key=lambda x: x.label):
                alias = f"  (aliases: {', '.join(e.aliases)})" if e.aliases else ""
                lines.append(f"  {e.uri} — \"{e.label}\"{alias}")
        return "\n".join(lines)
