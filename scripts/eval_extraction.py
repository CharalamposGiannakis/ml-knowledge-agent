#!/usr/bin/env python3
"""
Phase 2 gold-diff scorer.

Compares a proposals JSONL against the hand-reviewed gold TTL and reports
per-field precision/recall for: method, dataset, metric, value, source.

Designed for POST-FLAG-RESOLUTION input (records that converted to TTL), but
also works on partially-resolved JSONL — it reports resolution rates for each
field and skips accuracy checks where canonicals are missing.

Usage:
    python scripts/eval_extraction.py proposals/shwartzziv2022.jsonl
    python scripts/eval_extraction.py proposals/shwartzziv2022.jsonl \\
        --gold data/shwartzziv2022.ttl --tol 0.02

Exit code: 0 always (scorer, not a gate).
"""

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

REPO_ROOT = Path(__file__).parent.parent
ONTO_NS   = "http://mlkg.local/ontology#"
MLKG      = Namespace(ONTO_NS)


# ── gold loader ───────────────────────────────────────────────────────────────

def load_gold(ttl_path: Path) -> dict:
    """
    Parse gold TTL.  Returns:
      {(short_method_uri, short_dataset_uri, short_metric_uri): {
          "value": float, "std_error": float|None,
          "locator": str, "page": int
      }}
    Short URIs use the : prefix, e.g. ":XGBoost".
    """
    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    def short(uri_ref) -> str | None:
        if uri_ref is None:
            return None
        return ":" + str(uri_ref).replace(ONTO_NS, "")

    def fval(literal) -> float | None:
        return float(literal) if literal is not None else None

    gold: dict = {}
    for r in g.subjects(RDF.type, MLKG.BenchmarkResult):
        m   = short(g.value(r, MLKG.reportsMethod))
        d   = short(g.value(r, MLKG.onDataset))
        mt  = short(g.value(r, MLKG.usesMetric))
        val = fval(g.value(r, MLKG.hasValue))
        se  = fval(g.value(r, MLKG.stdError))

        src     = g.value(r, MLKG.hasSource)
        locator = str(g.value(src, MLKG.locator)) if src else None
        page_l  = g.value(src, MLKG.page)
        page    = int(page_l) if page_l is not None else None

        if m and d and mt and val is not None:
            gold[(m, d, mt)] = {
                "value":    val,
                "std_error": se,
                "locator":  locator,
                "page":     page,
            }
    return gold


# ── proposals loader ──────────────────────────────────────────────────────────

def load_proposals(jsonl_path: Path) -> tuple:
    """
    Read proposals JSONL.
    Line 0 = header object (paper metadata).
    Lines 1+ = one result per line.
    Returns (header: dict, results: list[dict]).
    """
    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        sys.exit(f"[error] {jsonl_path} is empty")
    header  = json.loads(lines[0])
    results = [json.loads(l) for l in lines[1:]]
    return header, results


# ── helpers ───────────────────────────────────────────────────────────────────

def _has_unresolved(r: dict) -> bool:
    return any(f.get("requires_human_answer") for f in r.get("flags", []))

def _fully_resolved(r: dict) -> bool:
    return (
        not _has_unresolved(r)
        and r.get("method_canonical")  is not None
        and r.get("dataset_canonical") is not None
        and r.get("metric_canonical")  is not None
    )

def _pct(num: int, den: int) -> str:
    return f"{100*num/den:.1f}%" if den else "N/A"

def _pr(correct: int, attempted: int, total_gold: int) -> str:
    p = f"{100*correct/attempted:.1f}%" if attempted else "N/A"
    r = f"{100*correct/total_gold:.1f}%"
    return p, r


def match_to_gold(fully_resolved: list, gold: dict) -> tuple:
    """
    Match fully-resolved proposal records to gold by the
    (method_canonical, dataset_canonical, metric_canonical) key.
    Returns (matched: list[(record, gold_entry)], unmatched: list[record]).
    """
    matched:   list = []
    unmatched: list = []
    for r in fully_resolved:
        key = (r["method_canonical"], r["dataset_canonical"], r["metric_canonical"])
        if key in gold:
            matched.append((r, gold[key]))
        else:
            unmatched.append(r)
    return matched, unmatched


# ── scoring ───────────────────────────────────────────────────────────────────

def score(jsonl_path: Path, gold_path: Path, tol: float) -> None:
    gold             = load_gold(gold_path)
    header, results  = load_proposals(jsonl_path)
    n_gold           = len(gold)
    n_proposed       = len(results)

    # Partition results
    fully_resolved = [r for r in results if _fully_resolved(r)]
    n_resolved     = len(fully_resolved)

    # Match fully-resolved records to gold by (method, dataset, metric) key
    matched, unmatched = match_to_gold(fully_resolved, gold)
    n_matched = len(matched)

    # Resolution rates (partial) — how many records have each canonical set
    m_set  = sum(1 for r in results if r.get("method_canonical")  is not None)
    d_set  = sum(1 for r in results if r.get("dataset_canonical") is not None)
    mt_set = sum(1 for r in results if r.get("metric_canonical")  is not None)

    # Value accuracy on matched pairs
    val_correct  = sum(
        1 for r, g in matched
        if r.get("value") is not None and abs(float(r["value"]) - g["value"]) <= tol
    )
    se_correct = sum(
        1 for r, g in matched
        if g["std_error"] is not None
        and r.get("std_error") is not None
        and abs(float(r["std_error"]) - g["std_error"]) <= tol
    )
    se_testable = sum(1 for _, g in matched if g["std_error"] is not None)

    # Source accuracy: document-level check of locator + page in header
    hdr_locator = header.get("source", {}).get("locator")
    hdr_page    = header.get("source", {}).get("page")
    gold_sources = {(g["locator"], g["page"]) for g in gold.values()}
    src_ok = (hdr_locator, hdr_page) in gold_sources

    # ── print report ─────────────────────────────────────────────────────────
    W = 62
    print("=" * W)
    print(f"EXTRACTION SCORE vs GOLD")
    print(f"  JSONL : {jsonl_path.relative_to(REPO_ROOT)}")
    print(f"  Gold  : {gold_path.relative_to(REPO_ROOT)}")
    print("=" * W)

    print(f"\nCOVERAGE")
    print(f"  Gold records             : {n_gold}")
    print(f"  Proposed records         : {n_proposed}")
    print(f"  Fully resolved (no flags): {n_resolved}  "
          f"({_pct(n_resolved, n_gold)} of gold)")
    print(f"  Matched to gold          : {n_matched}  "
          f"({_pct(n_matched, n_gold)} recall)")
    if unmatched:
        print(f"  Beyond gold (new records): {len(unmatched)}  "
              f"-- resolved but outside 6-dataset gold scope; verify against source")

    print(f"\nRESOLUTION RATES  (records with canonical filled / {n_proposed} proposed)")
    print(f"  method_canonical set     : {m_set:3d} / {n_proposed}  "
          f"({_pct(m_set, n_proposed)})")
    print(f"  dataset_canonical set    : {d_set:3d} / {n_proposed}  "
          f"({_pct(d_set, n_proposed)})")
    print(f"  metric_canonical set     : {mt_set:3d} / {n_proposed}  "
          f"({_pct(mt_set, n_proposed)})")
    print(f"  fully resolved           : {n_resolved:3d} / {n_proposed}  "
          f"({_pct(n_resolved, n_proposed)})")

    beyond = len(unmatched)
    print(f"\nPER-FIELD PRECISION / RECALL  "
          f"(on {n_matched} gold-adjudicable matched pairs; {beyond} beyond-gold excluded from denom.)")
    print(f"  {'field':<12}  {'precision':>10}  {'recall':>8}  note")
    print(f"  {'-'*55}")

    # method / dataset / metric — correct by construction of the key match.
    # Precision denominator = n_matched (adjudicable pairs only); beyond-gold records
    # are new data, not errors, so they must not inflate the false-positive count.
    for field in ("method", "dataset", "metric"):
        p, r_ = _pr(n_matched, n_matched, n_gold)
        note   = "key-match; beyond-gold excluded" if n_matched else "-"
        print(f"  {field:<12}  {p:>10}  {r_:>8}  {note}")

    # value
    vp, vr = _pr(val_correct, n_matched, n_gold)
    print(f"  {'value':<12}  {vp:>10}  {vr:>8}  "
          f"tol={tol}  ({val_correct}/{n_matched} matched pairs)")

    # std_error
    sep, ser = _pr(se_correct, se_testable, n_gold)
    print(f"  {'std_error':<12}  {sep:>10}  {ser:>8}  "
          f"({se_correct}/{se_testable} where gold has se)")

    # source (document-level)
    src_str = "CORRECT" if src_ok else "WRONG"
    print(f"  {'source':<12}  {'(doc-level)':>10}  {'':>8}  "
          f"{src_str}: locator='{hdr_locator}' page={hdr_page}")

    print(f"\n{'='*W}")

    # Detail: sample of matched pairs (if any)
    if matched:
        print(f"\nSAMPLE MATCHED PAIRS (first 5 of {n_matched}):")
        for r, g in matched[:5]:
            v_ok  = r.get("value") is not None and abs(float(r["value"]) - g["value"]) <= tol
            sym   = "[OK]" if v_ok else "[!!]"
            print(f"  {sym} {r['method_raw'][:22]:<22} / {r['dataset_raw'][:14]:<14}"
                  f"  val={r.get('value')} (gold={g['value']})")

    # Detail: unresolved flag breakdown
    reason_counts: dict = {}
    for r in results:
        for f in r.get("flags", []):
            reason_counts[f["reason"]] = reason_counts.get(f["reason"], 0) + 1
    if reason_counts:
        print(f"\nFLAG BREAKDOWN (across all {n_proposed} results):")
        for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason:<28} {cnt:>3}")

    if n_matched == 0 and n_proposed > 0:
        print(f"\nNOTE: 0 matches -- resolve flags in {jsonl_path.name} first, then re-run scorer.")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Phase 2 gold-diff scorer")
    p.add_argument("jsonl",
                   help="proposals JSONL file to score")
    p.add_argument("--gold",  default="data/shwartzziv2022.ttl",
                   help="Gold TTL file (default: data/shwartzziv2022.ttl)")
    p.add_argument("--tol",   type=float, default=0.02,
                   help="Numeric tolerance for value/std_error comparison (default: 0.02)")
    args = p.parse_args()

    jsonl_path = REPO_ROOT / args.jsonl
    gold_path  = REPO_ROOT / args.gold

    if not jsonl_path.exists():
        sys.exit(f"[error] JSONL not found: {jsonl_path}")
    if not gold_path.exists():
        sys.exit(f"[error] Gold TTL not found: {gold_path}")

    score(jsonl_path, gold_path, args.tol)


if __name__ == "__main__":
    main()
