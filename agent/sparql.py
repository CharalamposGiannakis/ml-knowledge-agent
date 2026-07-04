"""SPARQL SELECT backends for the query agent.

Read-only by design (ADR-016): the Fuseki backend reuses scripts/query.py's
anonymous client, so no credentials ever accompany a SELECT and the agent
physically cannot issue an UPDATE (Fuseki's shiro.ini only opens /query and
/sparql to anon).

Both backends return the same simplified row shape:
    list[dict[str, str]]  — variable name -> lexical value
so operations and tests are backend-agnostic.
"""
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_scripts_query():
    """Import scripts/query.py (not a package) without touching sys.path."""
    spec = importlib.util.spec_from_file_location(
        "mlkg_scripts_query", REPO_ROOT / "scripts" / "query.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FusekiBackend:
    """SELECTs against live Fuseki through scripts/query.py (anonymous POST)."""

    def __init__(self):
        self._query = _load_scripts_query().query

    def select(self, sparql: str) -> list:
        data = self._query(sparql)
        cols = data["head"]["vars"]
        return [
            {c: b[c]["value"] for c in cols if c in b}
            for b in data["results"]["bindings"]
        ]


class RdflibBackend:
    """In-memory backend over an rdflib.Graph — used by tests and offline runs."""

    def __init__(self, graph):
        self.graph = graph

    def select(self, sparql: str) -> list:
        result = self.graph.query(sparql)
        rows = []
        for binding in result:
            d = binding.asdict()
            rows.append({str(k): str(v) for k, v in d.items() if v is not None})
        return rows
