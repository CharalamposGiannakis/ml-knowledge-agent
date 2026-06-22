#!/usr/bin/env python3
"""Layer-3 transient OWL consistency check (periodic, optional).

Usage:
    python3 scripts/consistency.py                    # checks all data/*.ttl
    python3 scripts/consistency.py data/foo.ttl ...   # checks specific files

Loads ontology + data file(s) into a TEMPORARY in-memory graph, runs an OWL RL
deductive closure, and checks for owl:Nothing membership (the canonical OWL
contradiction signal). Exits 0 if consistent, 1 if inconsistent.

CRITICAL (ADR-015): inferred triples are NEVER written to disk or to Fuseki.
The graph object is local and discarded when the process exits.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_FILE = ROOT / "ontology" / "mlkg.ttl"


def main() -> None:
    try:
        import owlrl
        from rdflib import OWL, RDF, Graph
    except ImportError:
        print("consistency.py requires: pip install owlrl rdflib", file=sys.stderr)
        sys.exit(2)

    if len(sys.argv) > 1:
        data_files = [Path(f) for f in sys.argv[1:]]
    else:
        data_files = sorted((ROOT / "data").glob("*.ttl"))

    if not data_files:
        print("No data files found. Pass .ttl paths as arguments or populate data/.", file=sys.stderr)
        sys.exit(2)

    # Transient in-memory graph — never written to disk or Fuseki (ADR-015).
    g = Graph()
    g.parse(str(ONTOLOGY_FILE), format="turtle")
    for f in data_files:
        f = Path(f)
        if not f.exists():
            print(f"warning: {f} not found, skipping", file=sys.stderr)
            continue
        g.parse(str(f), format="turtle")

    triple_count = len(g)
    print(f"Loaded {triple_count} asserted triples; running OWL RL closure (transient) ...")
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)

    nothing_members = list(g.subjects(RDF.type, OWL.Nothing))
    if nothing_members:
        print(f"INCONSISTENT: {len(nothing_members)} individual(s) typed owl:Nothing")
        for n in nothing_members[:10]:
            print(f"  {n}")
        sys.exit(1)
    else:
        print(
            f"CONSISTENT: OWL RL closure found no contradictions "
            f"({len(g)} total triples after closure; none persisted)."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
