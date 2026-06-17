#!/usr/bin/env python3
"""Minimal SPARQL client for the MLKG Fuseki endpoint.

Phase 0: a smoke-test query runner.
Later phases: the agent reuses this same query() against the live graph.

Usage:
    python3 scripts/query.py                 # runs the default count query
    python3 scripts/query.py < my_query.rq   # runs a query piped on stdin
"""
import os
import sys

import requests

FUSEKI_URL = os.environ.get("FUSEKI_URL", "http://localhost:3030")
DATASET = os.environ.get("DATASET", "mlkg")

DEFAULT_QUERY = """
PREFIX : <http://mlkg.local/ontology#>
SELECT (COUNT(?r) AS ?benchmark_results) WHERE { ?r a :BenchmarkResult }
"""


def query(sparql: str) -> dict:
    """Run a SPARQL SELECT and return the JSON results object."""
    resp = requests.post(
        f"{FUSEKI_URL}/{DATASET}/query",
        data={"query": sparql},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def print_table(data: dict) -> None:
    cols = data["head"]["vars"]
    print("\t".join(cols))
    for row in data["results"]["bindings"]:
        print("\t".join(row.get(c, {}).get("value", "") for c in cols))


if __name__ == "__main__":
    sparql = sys.stdin.read() if not sys.stdin.isatty() else DEFAULT_QUERY
    print_table(query(sparql))
