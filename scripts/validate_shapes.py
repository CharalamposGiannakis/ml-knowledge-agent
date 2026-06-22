#!/usr/bin/env python3
"""SHACL pre-load gate.

Usage:
    python3 scripts/validate_shapes.py <data.ttl>

Validates <data.ttl> against ontology/shapes.ttl (structural shapes) combined
with ontology/mlkg.ttl (class membership for sh:class checks).
Exits 0 if conformant; prints the violation report to stderr and exits 1 if not.
"""
import sys
from pathlib import Path

import pyshacl
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent
SHAPES_FILE = ROOT / "ontology" / "shapes.ttl"
ONTOLOGY_FILE = ROOT / "ontology" / "mlkg.ttl"


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <data.ttl>", file=sys.stderr)
        sys.exit(2)

    data_path = Path(sys.argv[1]).resolve()
    if not data_path.exists():
        print(f"error: {data_path} not found", file=sys.stderr)
        sys.exit(2)

    shapes_graph = Graph().parse(str(SHAPES_FILE), format="turtle")

    # Merge data + ontology into one graph so that class membership (e.g.
    # :XGBoost a :Method) and property values (e.g. :CrossEntropyLoss
    # :optimizationDirection :LowerIsBetter) are both visible to the shapes.
    # This mirrors the combined graph state that Fuseki holds after both the
    # ontology and the data file have been loaded.
    data_graph = Graph().parse(str(ONTOLOGY_FILE), format="turtle")
    data_graph += Graph().parse(str(data_path), format="turtle")

    conforms, _, results_text = pyshacl.validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
        meta_shacl=False,
        advanced=False,
        js=False,
        debug=False,
    )

    if conforms:
        print(f"SHACL PASS: {data_path.name} conforms.")
        sys.exit(0)
    else:
        print(f"SHACL FAIL: {data_path.name} does not conform.\n", file=sys.stderr)
        print(results_text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
