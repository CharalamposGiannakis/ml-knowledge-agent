#!/usr/bin/env python3
"""
Phase 2 extraction pipeline — v1 cut.

PDF → PyMuPDF render → Anthropic vision (Opus) → strict JSON →
normalise against Fuseki graph → TTL emit → rdflib validate →
proposals/<paper_id>.jsonl + proposals/<paper_id>_proposed.ttl

Usage:
    python scripts/phase2_extract.py
    python scripts/phase2_extract.py --pdf pdfs/shwartzziv2022.pdf --page 6 \
        --paper-id shwartzziv2022 --locator "Table 2"

Requires:
    - Fuseki running:    docker compose up -d
    - .env containing:  ANTHROPIC_API_KEY=sk-ant-...
    - Packages:         pymupdf anthropic rdflib python-dotenv requests
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
import requests
from anthropic import Anthropic
from dotenv import load_dotenv
from rdflib import Graph

# ── constants ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
ONTO_NS = "http://mlkg.local/ontology#"
SPARQL_ENDPOINT = "http://localhost:3030/mlkg/query"
MODEL = "claude-opus-4-8"
RENDER_DPI = 200

# Maps paper_id + locator → known RDF URIs (avoids SPARQL look-up for phase-1 data)
PAPER_META: dict = {
    "shwartzziv2022": {
        "paper_uri": ":paper_sz2022",
        "Table 2":   ":src_sz2022_t2",
    }
}

TTL_PREFIXES = """\
@prefix :     <http://mlkg.local/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
"""

# JSON schema template shown to the model (placeholders filled at call time)
_SCHEMA_TEMPLATE = """\
{
  "schema_version": "1.0",
  "paper_id": "__PAPER_ID__",
  "extracted_by": "claude-opus-4-8",
  "source": {
    "locator": "__LOCATOR__",
    "page": __PAGE__,
    "caption": "<exact caption text you see on the page>"
  },
  "table_flags": [],
  "results": [
    {
      "method_raw":       "<exact method text from the table row>",
      "method_canonical": null,
      "dataset_raw":      "<exact column header text for the dataset>",
      "dataset_canonical": null,
      "metric_raw":       "<metric + unit/scaling as stated in caption>",
      "metric_canonical": null,
      "value":            0.0,
      "std_error":        0.0,
      "raw_cell":         "<verbatim cell text, e.g. '78.93 \\u00b1 0.73'>",
      "conditions":       [],
      "conditions_complete": false,
      "flags":            []
    }
  ]
}"""


# ── 1. render ─────────────────────────────────────────────────────────────────

def render_page(pdf_path: Path, page_num: int, dpi: int = RENDER_DPI) -> bytes:
    """Render page_num (1-based) to PNG bytes at the given DPI."""
    doc = fitz.open(str(pdf_path))
    if not (1 <= page_num <= len(doc)):
        doc.close()
        raise ValueError(f"Page {page_num} out of range (1–{len(doc)})")
    page = doc[page_num - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    png = pix.tobytes("png")
    doc.close()
    print(f"[render]  page {page_num} -> {pix.width}x{pix.height}px  {len(png)//1024}KB")
    return png


# ── 2. vocabulary ─────────────────────────────────────────────────────────────

def fetch_vocabulary(endpoint: str) -> dict:
    """
    SPARQL the live graph for every Method/Dataset/Metric with its
    rdfs:label and skos:altLabel.

    Returns { casefold_string: {"uri": ":XGBoost", "label": "XGBoost", "type": "Method"} }.
    The first entry wins on casefold collision (labels should be unique).
    """
    query = """
PREFIX :    <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?uri ?label ?altLabel ?type WHERE {
  VALUES ?type { :Method :Dataset :Metric }
  ?uri a ?type ; rdfs:label ?label .
  OPTIONAL { ?uri skos:altLabel ?altLabel }
}
ORDER BY ?type ?label
"""
    try:
        resp = requests.post(
            endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(
            f"[vocab]   Fuseki unreachable at {endpoint}: {exc}\n"
            "          Run:  docker compose up -d"
        )

    vocab: dict = {}
    for row in resp.json()["results"]["bindings"]:
        full_uri = row["uri"]["value"]
        short_uri = ":" + full_uri.replace(ONTO_NS, "")
        label     = row["label"]["value"]
        etype     = row["type"]["value"].replace(ONTO_NS, "")
        entry     = {"uri": short_uri, "label": label, "type": etype}

        vocab.setdefault(label.strip().casefold(), entry)
        if "altLabel" in row:
            vocab.setdefault(row["altLabel"]["value"].strip().casefold(), entry)

    # Print a concise summary by type
    by_type: dict = {}
    for e in vocab.values():
        by_type.setdefault(e["type"], set()).add(e["label"])
    for t in ("Method", "Dataset", "Metric"):
        labels = sorted(by_type.get(t, set()))
        snippet = ", ".join(labels[:6]) + ("..." if len(labels) > 6 else "")
        print(f"[vocab]   {t}s ({len(labels)}): {snippet}")

    return vocab


# ── 3. extract ────────────────────────────────────────────────────────────────

def call_vision_llm(
    client: Anthropic,
    png: bytes,
    paper_id: str,
    locator: str,
    page: int,
    vocab: dict,
) -> dict:
    """
    Single Opus vision call.  Returns the parsed JSON extraction document.
    The model outputs *_raw verbatim; normalisation is done in code (step 4).
    """
    # Group vocab labels by type for the prompt
    by_type: dict = {}
    for e in vocab.values():
        by_type.setdefault(e["type"], set()).add(e["label"])
    vocab_block = "\n".join(
        f"  {t}s: {', '.join(sorted(labels))}"
        for t, labels in sorted(by_type.items())
    )

    schema = (
        _SCHEMA_TEMPLATE
        .replace("__PAPER_ID__", paper_id)
        .replace("__LOCATOR__", locator)
        .replace("__PAGE__", str(page))
    )

    prompt = f"""Extract every numeric result from the benchmark table on this page.

KNOWN VOCABULARY — canonical entity names in our knowledge base (for your reference;
do NOT use these to rewrite what the table says — always copy table text verbatim):
{vocab_block}

INSTRUCTIONS
1. Output ONLY a single valid JSON object. No markdown fences, no prose, no indentation.
   Use COMPACT JSON: each result object on ONE line, no extra whitespace.
2. Extract EVERY row from the results table. Do not skip any method.
3. method_raw / dataset_raw / metric_raw: copy EXACTLY what appears in the table or
   its caption. Do not substitute canonical names.
4. raw_cell: verbatim cell text (e.g. "78.93 ± 0.73").
5. value: the primary numeric value (Python float).
   std_error: number after "±" (float), or null if none.
6. metric_raw: read from the table caption. Include the name and any unit or scaling
   factor (e.g. "cross-entropy ×100"). If different columns use different metrics,
   set metric_raw per result accordingly.
7. Leave all *_canonical fields as null. Leave flags as [].
   conditions: [].  conditions_complete: false.
8. Fill source.caption with the exact caption text visible on the page.

OUTPUT STRUCTURE (one entry in "results" per table cell):
{schema}"""

    print(f"[extract] Calling {MODEL} (vision, {len(png)//1024}KB)  max_tokens=16384...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.standard_b64encode(png).decode(),
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    stop_reason = response.stop_reason
    raw = response.content[0].text.strip()
    print(f"[extract] stop_reason={stop_reason!r}  output_tokens={response.usage.output_tokens}")

    # Always save raw output for debugging / audit
    raw_path = REPO_ROOT / "proposals" / f"{paper_id}_llm_raw.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8")
    print(f"[extract] Raw response saved -> {raw_path.relative_to(REPO_ROOT)}")

    if stop_reason == "max_tokens":
        sys.exit(
            f"[extract] TRUNCATED: model hit max_tokens=16384 before finishing.\n"
            f"          Increase max_tokens in call_vision_llm() and re-run."
        )

    # Strip markdown fences if the model adds them despite instructions
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"[extract] JSON parse error: {exc}\n          Raw response -> {raw_path}")

    print(f"[extract] {len(doc.get('results', []))} results from model")
    return doc


# ── 4. normalise ──────────────────────────────────────────────────────────────

def _parse_cell(raw_cell: str) -> tuple:
    """Parse 'VALUE ± ERROR' string → (value, std_error) or (None, None)."""
    text = raw_cell.strip().replace("±", "±").replace("+/-", "±")
    m = re.match(
        r"^\s*([\d,]+\.?\d*(?:[eE][+\-]?\d+)?)"
        r"(?:\s*±\s*([\d,]+\.?\d*(?:[eE][+\-]?\d+)?))?\s*$",
        text,
    )
    if not m:
        return None, None
    val = float(m.group(1).replace(",", ""))
    err = float(m.group(2).replace(",", "")) if m.group(2) else None
    return val, err


def _normalise_result(result: dict, vocab: dict) -> dict:
    """
    Match *_raw fields against vocab; fill *_canonical or raise reason-coded flags.
    Reason codes: no_alias_match, metric_not_in_vocab, value_parse_mismatch,
                  missing_required, type_mismatch.
    """
    flags: list = []

    for prefix in ("method", "dataset", "metric"):
        raw = result.get(f"{prefix}_raw")

        if not raw:
            flags.append({
                "field": f"{prefix}_raw",
                "reason": "missing_required",
                "question": f"Required field '{prefix}_raw' is absent.",
                "options": [],
                "requires_human_answer": True,
            })
            continue

        entry = vocab.get(raw.strip().casefold())

        if entry is None:
            # Metric gets a distinct reason code (also needs direction at review)
            reason = "metric_not_in_vocab" if prefix == "metric" else "no_alias_match"
            etype  = prefix.capitalize()
            q_suffix = " (also: set optimizationDirection at review)" if prefix == "metric" else ""
            flags.append({
                "field": f"{prefix}_canonical",
                "reason": reason,
                "question": (
                    f"'{raw}' matched no known {etype}{q_suffix}. "
                    f"New entity, or alias of an existing one?"
                ),
                "options": [f"new_{prefix}", "alias_of:<uri>", "variant_of:<uri>"],
                "requires_human_answer": True,
            })
        else:
            # Resolved — fill canonical and verify type
            result[f"{prefix}_canonical"] = entry["uri"]
            expected = prefix.capitalize()
            if entry["type"] != expected:
                flags.append({
                    "field": f"{prefix}_canonical",
                    "reason": "type_mismatch",
                    "question": (
                        f"'{raw}' resolved to {entry['uri']} (type {entry['type']}), "
                        f"expected {expected}."
                    ),
                    "options": [f"confirm_{entry['uri']}", "discard"],
                    "requires_human_answer": True,
                })

    # value_parse_mismatch: re-parse raw_cell and cross-check stated value/std_error
    raw_cell    = result.get("raw_cell", "")
    stated_val  = result.get("value")
    stated_err  = result.get("std_error")

    if raw_cell and stated_val is not None:
        parsed_val, parsed_err = _parse_cell(raw_cell)
        if parsed_val is not None and abs(parsed_val - float(stated_val)) > 1e-3:
            flags.append({
                "field": "value",
                "reason": "value_parse_mismatch",
                "question": (
                    f"Re-parsing '{raw_cell}' -> {parsed_val}, "
                    f"but value field = {stated_val}."
                ),
                "options": [f"use_parsed:{parsed_val}", f"keep_stated:{stated_val}"],
                "requires_human_answer": True,
            })
        if (
            parsed_err is not None
            and stated_err is not None
            and abs(parsed_err - float(stated_err)) > 1e-3
        ):
            flags.append({
                "field": "std_error",
                "reason": "value_parse_mismatch",
                "question": (
                    f"Re-parsing '{raw_cell}' -> std_error={parsed_err}, "
                    f"but std_error field = {stated_err}."
                ),
                "options": [f"use_parsed:{parsed_err}", f"keep_stated:{stated_err}"],
                "requires_human_answer": True,
            })

    result["flags"] = flags
    return result


def normalise_extraction(doc: dict, vocab: dict) -> dict:
    doc["results"] = [_normalise_result(r, vocab) for r in doc.get("results", [])]
    return doc


# ── 5. emit + validate ────────────────────────────────────────────────────────

def _fmt_decimal(v) -> str:
    """Format as Turtle decimal literal (always contains a decimal point)."""
    s = repr(float(v))
    return s if "." in s else s + ".0"


def _slug(text: str, maxlen: int = 22) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", text.lower()))[:maxlen].strip("_")


def _is_clean(result: dict) -> bool:
    return not any(f["requires_human_answer"] for f in result.get("flags", []))


def emit_ttl(doc: dict) -> str:
    """
    Deterministically convert clean records to Turtle.
    Records with any unresolved requires_human_answer flag are skipped (ADR-012).
    """
    paper_id = doc["paper_id"]
    source   = doc["source"]
    locator  = source["locator"]
    meta     = PAPER_META.get(paper_id, {})
    paper_uri = meta.get("paper_uri", ":paper_unknown")
    src_uri   = meta.get(locator, f":src_{_slug(paper_id)}_proposed")

    clean = [r for r in doc["results"] if _is_clean(r)]

    lines = [
        TTL_PREFIXES,
        f"# Proposed triples — {paper_id} · {locator} · p.{source['page']}",
        f"# Extracted: {datetime.now().isoformat(timespec='seconds')}",
        f"# Model: {doc.get('extracted_by', MODEL)}",
        f"# !! REVIEW REQUIRED before loading to Fuseki (CLAUDE.md rule 1) !!",
        "",
        f"# Source location (idempotent if already in graph)",
        f"{src_uri} a :SourceLocation ;",
        f"    :fromPaper {paper_uri} ;",
        f"    :locator {json.dumps(locator)} ;",
        f"    :page {source['page']} .",
        "",
    ]

    if not clean:
        lines.append("# No clean records — all results carry unresolved flags.")
        return "\n".join(lines)

    for r in clean:
        uri = f":prop_{_slug(r['method_raw'])}_{_slug(r['dataset_raw'])}_{paper_id[:8]}"
        block = [
            f"{uri} a :BenchmarkResult ;",
            f"    :reportsMethod {r['method_canonical']} ;",
            f"    :onDataset     {r['dataset_canonical']} ;",
            f"    :usesMetric    {r['metric_canonical']} ;",
            f"    :hasValue      {_fmt_decimal(r['value'])} ;",
        ]
        if r.get("std_error") is not None:
            block.append(f"    :stdError {_fmt_decimal(r['std_error'])} ;")
        block += [
            f"    :hasSource     {src_uri} ;",
            f"    :extractedBy   {json.dumps(doc.get('extracted_by', MODEL))} ;",
            f"    :conditionsComplete false .",
        ]
        lines += block
        lines.append("")

    return "\n".join(lines)


def validate_ttl(ttl_str: str, label: str = "") -> bool:
    g = Graph()
    try:
        g.parse(data=ttl_str, format="turtle")
        print(f"[validate] {label}rdflib OK — {len(g)} triples")
        return True
    except Exception as exc:
        print(f"[validate] {label}PARSE ERROR: {exc}", file=sys.stderr)
        return False


# ── 6. write proposals ────────────────────────────────────────────────────────

def write_proposals(doc: dict) -> tuple:
    """
    Write proposals/<paper_id>.jsonl and proposals/<paper_id>_proposed.ttl.
    Returns (jsonl_path, ttl_path).
    """
    out_dir  = REPO_ROOT / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_id = doc["paper_id"]

    total     = len(doc["results"])
    n_clean   = sum(1 for r in doc["results"] if _is_clean(r))
    n_flagged = total - n_clean

    # JSONL: header line then one result per line
    jsonl_path = out_dir / f"{paper_id}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        header = {k: v for k, v in doc.items() if k != "results"}
        header["total_results"]  = total
        header["clean_results"]  = n_clean
        header["flagged_results"] = n_flagged
        fh.write(json.dumps(header) + "\n")
        for r in doc["results"]:
            fh.write(json.dumps(r) + "\n")
    print(f"[write]   {jsonl_path.relative_to(REPO_ROOT)}  ({total+1} lines)")

    # TTL for clean records
    ttl_str  = emit_ttl(doc)
    ttl_path = out_dir / f"{paper_id}_proposed.ttl"
    ttl_path.write_text(ttl_str, encoding="utf-8")
    print(f"[write]   {ttl_path.relative_to(REPO_ROOT)}  ({n_clean} clean records)")
    validate_ttl(ttl_str, label=f"{paper_id}_proposed.ttl: ")

    return jsonl_path, ttl_path


# ── 7. summary ────────────────────────────────────────────────────────────────

# Gold values from hand-reviewed data/shwartzziv2022.ttl for spot-checking.
# Key: (method_substring, dataset_substring) both casefold.
_GOLD = {
    ("xgboost",    "rossmann"): (490.18, 1.19),
    ("xgboost",    "gesture"):  (80.64,  0.80),
    ("node",       "gesture"):  (92.12,  0.82),
    ("node",       "higgs"):    (21.19,  0.69),
    ("tabnet",     "gesture"):  (96.42,  0.87),
    ("tabnet",     "covertype"):(3.01,   0.08),
    ("dnf",        "gas"):      (1.44,   0.09),
    ("1d-cnn",     "eye"):      (67.90,  0.64),
}


def print_summary(doc: dict):
    results   = doc["results"]
    total     = len(results)
    clean     = [r for r in results if _is_clean(r)]
    flagged   = [r for r in results if not _is_clean(r)]

    print(f"\n{'='*62}")
    print(f"EXTRACTION SUMMARY — {doc['paper_id']}  {doc['source']['locator']}")
    print(f"{'='*62}")
    print(f"  Results extracted  : {total}")
    print(f"  Clean -> TTL        : {len(clean)}")
    print(f"  Flagged (review)   : {len(flagged)}")

    # Flag reason breakdown
    reason_counts: dict = {}
    for r in results:
        for f in r.get("flags", []):
            reason_counts[f["reason"]] = reason_counts.get(f["reason"], 0) + 1
    if reason_counts:
        print("\n  Flag reason breakdown:")
        for reason, n in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"    {reason:<28} {n:>3}")

    # Spot-check extracted values against gold
    print("\n  Value spot-check vs gold (data/shwartzziv2022.ttl):")
    hits = misses = checked = 0
    for r in results:
        m_cf = r.get("method_raw",  "").casefold()
        d_cf = r.get("dataset_raw", "").casefold()
        for (m_key, d_key), (gold_val, gold_err) in _GOLD.items():
            if m_key in m_cf and d_key in d_cf:
                checked += 1
                v = r.get("value")
                e = r.get("std_error")
                v_ok = v is not None and abs(float(v) - gold_val) <= 0.02
                e_ok = e is not None and abs(float(e) - gold_err) <= 0.02
                sym  = "[OK]" if v_ok else "[!!]"
                print(f"    [{sym}] {r['method_raw'][:30]:<30} / "
                      f"{r['dataset_raw'][:12]:<12}  "
                      f"val={v} (gold={gold_val}) "
                      f"  se={e} (gold={gold_err})")
                if v_ok:
                    hits += 1
                else:
                    misses += 1
    if checked:
        print(f"\n    Value accuracy: {hits}/{checked} spot values within 0.02 of gold")

    # Sample flagged
    if flagged:
        print(f"\n  Sample flagged records (first 3 of {len(flagged)}):")
        for r in flagged[:3]:
            print(f"    {r.get('method_raw','?')[:30]} / {r.get('dataset_raw','?')}")
            for f in r["flags"][:2]:
                print(f"      [{f['reason']}] {f['question'][:80]}")

    print(f"{'='*62}\n")


# ── main ──────────────────────────────────────────────────────────────────────

def _make_mock_extraction(paper_id: str, locator: str, page: int) -> dict:
    """
    Realistic mock of what Opus would extract from Shwartz-Ziv Table 2.
    Uses abbreviated names as they appear in the table (not canonical graph labels),
    so normalisation flags fire exactly as they would on real model output.
    Values are identical to the hand-reviewed gold (data/shwartzziv2022.ttl).

    Useful for testing stages 4–6 without spending API credits.
    """
    # (method_raw, metric for this method's Rossmann column, metric for CE columns)
    # Table columns: Rossmann (MSE), CoverType, Higgs, Gas, Eye, Gesture (all CE×100)
    rows = [
        # method_raw,                    Rossmann    CoverType  Higgs    Gas    Eye      Gesture
        ("XGBoost",                      490.18,1.19, 3.13,0.09, 21.62,0.33, 2.18,0.20, 56.07,0.65, 80.64,0.80),
        ("NODE",                         488.59,1.24, 4.15,0.13, 21.19,0.69, 2.17,0.18, 68.35,0.66, 92.12,0.82),
        ("DNF-Net",                      503.83,1.41, 3.96,0.11, 23.68,0.83, 1.44,0.09, 68.38,0.65, 86.98,0.74),
        ("TabNet",                       485.12,1.93, 3.01,0.08, 21.14,0.20, 1.92,0.14, 67.13,0.69, 96.42,0.87),
        ("1D-CNN",                       493.81,2.23, 3.51,0.13, 22.33,0.73, 1.79,0.19, 67.90,0.64, 97.89,0.82),
        ("Simple Ensemble",              488.57,2.14, 3.19,0.18, 22.46,0.38, 2.36,0.13, 58.72,0.67, 89.45,0.89),
        ("Deep Ensemble w/o XGB",        489.94,2.09, 3.52,0.10, 22.41,0.54, 1.98,0.13, 69.28,0.62, 93.50,0.75),
        ("Deep Ensemble w/ XGB",         485.33,1.29, 2.99,0.08, 22.34,0.81, 1.69,0.10, 59.43,0.60, 78.93,0.73),
    ]
    datasets = [
        ("Rossmann",  "MSE"),
        ("CoverType", "cross-entropy ×100"),
        ("Higgs",     "cross-entropy ×100"),
        ("Gas",       "cross-entropy ×100"),
        ("Eye",       "cross-entropy ×100"),
        ("Gesture",   "cross-entropy ×100"),
    ]

    results = []
    for row in rows:
        method = row[0]
        vals   = row[1:]   # 12 numbers: val0,se0, val1,se1, ...
        for i, (ds, metric) in enumerate(datasets):
            v, se = vals[i*2], vals[i*2+1]
            results.append({
                "method_raw":       method,
                "method_canonical": None,
                "dataset_raw":      ds,
                "dataset_canonical": None,
                "metric_raw":       metric,
                "metric_canonical": None,
                "value":            v,
                "std_error":        se,
                "raw_cell":         f"{v} ± {se}",
                "conditions":       [],
                "conditions_complete": False,
                "flags":            [],
            })

    return {
        "schema_version": "1.0",
        "paper_id":       paper_id,
        "extracted_by":   "MOCK (--mock-llm flag; no API call made)",
        "source": {
            "locator": locator,
            "page":    page,
            "caption": (
                "Table 2. Test error on tabular benchmarks. "
                "Cross-entropy values ×100. Rossmann uses MSE. Lower is better."
            ),
        },
        "table_flags": [],
        "results":     results,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 2 extraction pipeline — v1")
    p.add_argument("--pdf",      default="pdfs/shwartzziv2022.pdf")
    p.add_argument("--page",     type=int, default=6,
                   help="1-based page number containing the table")
    p.add_argument("--paper-id", default="shwartzziv2022")
    p.add_argument("--locator",  default="Table 2")
    p.add_argument("--fuseki",   default=SPARQL_ENDPOINT)
    p.add_argument("--mock-llm", action="store_true",
                   help="Skip the API call; use realistic mock extraction data "
                        "(tests stages 1,2,4,5,6 without spending API credits)")
    return p.parse_args()


def main():
    load_dotenv(REPO_ROOT / ".env")
    args     = parse_args()
    pdf_path = REPO_ROOT / args.pdf

    if not pdf_path.exists():
        sys.exit(f"[error] PDF not found: {pdf_path}")

    # 1. Render (always — confirms PyMuPDF works regardless of mock flag)
    png = render_page(pdf_path, args.page)

    # 2. Vocabulary from live graph
    vocab = fetch_vocabulary(args.fuseki)

    # 3. Vision extraction (or mock)
    if args.mock_llm:
        print("[extract] --mock-llm: skipping API call, using realistic mock data")
        doc = _make_mock_extraction(args.paper_id, args.locator, args.page)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit(
                "[error] ANTHROPIC_API_KEY not set.\n"
                "        Add to .env:  ANTHROPIC_API_KEY=sk-ant-...\n"
                "        Or run with --mock-llm to test without an API call."
            )
        client = Anthropic(api_key=api_key)
        doc = call_vision_llm(client, png, args.paper_id, args.locator, args.page, vocab)

    # 4. Normalise
    doc = normalise_extraction(doc, vocab)

    # 5+6. Emit TTL, validate, write proposals/
    write_proposals(doc)

    # 7. Human-readable summary
    print_summary(doc)

    print("[done]  Phase 2 v1 complete.")
    print("[done]  Check proposals/ — DO NOT load to Fuseki without review (CLAUDE.md rule 1).")


if __name__ == "__main__":
    main()
