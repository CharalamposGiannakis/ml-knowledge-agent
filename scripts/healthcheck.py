#!/usr/bin/env python3
"""Layer-2 SPARQL invariant health checks.

Usage:
    python3 scripts/healthcheck.py

Runs queries A-D from docs/health_checks.md against the live Fuseki endpoint.
Prints a PASS/FAIL line per check; exits 0 if all pass, 1 if any fail.
"""
import os
import sys

import requests

FUSEKI_URL = os.environ.get("FUSEKI_URL", "http://localhost:3030")
DATASET = os.environ.get("DATASET", "mlkg")

_P = (
    "PREFIX : <http://mlkg.local/ontology#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)

CHECKS = [
    {
        "id": "A",
        "desc": "metrics missing a direction (expect 0 rows)",
        "query": _P + "SELECT ?m WHERE { ?m a :Metric . FILTER NOT EXISTS { ?m :optimizationDirection ?d } }",
        "mode": "zero_rows",
    },
    {
        "id": "B",
        "desc": "results pointing at an undefined method (expect 0 rows)",
        "query": _P + (
            "SELECT ?r WHERE { ?r a :BenchmarkResult ; :reportsMethod ?m .\n"
            "  FILTER NOT EXISTS { ?m rdfs:label ?l } }"
        ),
        "mode": "zero_rows",
    },
    {
        "id": "C",
        "desc": "duplicate results same method+dataset+metric (expect 0 rows, guards ADR-014)",
        "query": _P + (
            "SELECT ?a ?b WHERE {\n"
            "  ?a a :BenchmarkResult ; :reportsMethod ?m ; :onDataset ?d ; :usesMetric ?me .\n"
            "  ?b a :BenchmarkResult ; :reportsMethod ?m ; :onDataset ?d ; :usesMetric ?me .\n"
            "  FILTER(STR(?a) < STR(?b)) }"
        ),
        "mode": "zero_rows",
    },
    {
        "id": "D",
        "desc": "flagship XGBoost/Gesture/CrossEntropyLoss = 80.64 (expect 1 row)",
        "query": _P + (
            "SELECT ?v WHERE { ?r :reportsMethod :XGBoost ; :onDataset :ds_gesture ;\n"
            "  :usesMetric :CrossEntropyLoss ; :hasValue ?v }"
        ),
        "mode": "value",
        "expected": 80.64,
    },
]


def _sparql(query: str) -> list[dict]:
    resp = requests.post(
        f"{FUSEKI_URL}/{DATASET}/query",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def main() -> None:
    all_pass = True
    for chk in CHECKS:
        try:
            rows = _sparql(chk["query"])
        except Exception as exc:
            print(f"FAIL {chk['id']}: {chk['desc']} — {exc}")
            all_pass = False
            continue

        if chk["mode"] == "zero_rows":
            if rows:
                print(f"FAIL {chk['id']}: {chk['desc']} — got {len(rows)} row(s)")
                for r in rows[:5]:
                    print(f"       {r}")
                all_pass = False
            else:
                print(f"PASS {chk['id']}: {chk['desc']}")

        elif chk["mode"] == "value":
            expected = float(chk["expected"])
            if len(rows) != 1:
                print(f"FAIL {chk['id']}: {chk['desc']} — expected 1 row, got {len(rows)}")
                all_pass = False
            else:
                val = float(rows[0]["v"]["value"])
                if abs(val - expected) < 1e-6:
                    print(f"PASS {chk['id']}: {chk['desc']} — {val}")
                else:
                    print(f"FAIL {chk['id']}: {chk['desc']} — expected {expected}, got {val}")
                    all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
