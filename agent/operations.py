"""Hand-written parameterised SPARQL operations + result shapers (ADR-018).

Every query the agent can run lives here, authored and tested as code. The
LLM only ever *names* an operation and supplies catalog URIs for its slots;
`build_sparql` validates each URI against a strict pattern before splicing,
and the loop has already checked catalog membership + entity type. No path
lets model-authored text reach the query string.

Winner/direction logic reads :optimizationDirection from the returned rows —
never hardcoded.

Adding an operation = one OperationSpec entry: slots, a SPARQL builder, a
shaper, and a one-line description for the planner prompt.
"""
import re
from dataclasses import dataclass

ONTO_NS = "http://mlkg.local/ontology#"
HIGHER = ONTO_NS + "HigherIsBetter"
LOWER = ONTO_NS + "LowerIsBetter"

# Only URIs of this exact shape may be spliced into a query. Catalog membership
# is checked by the loop before this; the regex is the last line of defence.
_SAFE_URI = re.compile(r"^http://mlkg\.local/ontology#[A-Za-z0-9_]+$")

PREFIXES = """\
PREFIX :     <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# Shared graph pattern: one BenchmarkResult row with labels, metric direction,
# and the full SourceLocation -> Paper citation chain.
_RESULT_VARS = (
    "?result ?method ?methodLabel ?dataset ?datasetLabel ?metric ?metricLabel "
    "?direction ?value ?stdErr ?seen ?locator ?page ?paperTitle ?paperYear"
)
_RESULT_BLOCK = """\
  ?result a :BenchmarkResult ;
          :reportsMethod ?method ;
          :onDataset ?dataset ;
          :usesMetric ?metric ;
          :hasValue ?value ;
          :hasSource ?src .
  ?method rdfs:label ?methodLabel .
  ?dataset rdfs:label ?datasetLabel .
  ?metric rdfs:label ?metricLabel ; :optimizationDirection ?direction .
  ?src :locator ?locator ; :page ?page ; :fromPaper ?paper .
  ?paper :title ?paperTitle ; :year ?paperYear .
  OPTIONAL { ?result :stdError ?stdErr }
  OPTIONAL { ?result :datasetSeenByModel ?seen }
"""


class SlotError(ValueError):
    """A slot value failed validation; the query is never built."""


def _uri(slots: dict, name: str) -> str:
    value = slots[name]
    if not isinstance(value, str) or not _SAFE_URI.fullmatch(value):
        raise SlotError(f"slot '{name}' is not a safe ontology URI: {value!r}")
    return f"<{value}>"


def _metric_clause(slots: dict) -> str:
    if slots.get("metric"):
        return f"  VALUES ?metric {{ {_uri(slots, 'metric')} }}\n"
    return ""


def _citation(row: dict) -> dict:
    return {
        "paper": row["paperTitle"],
        "year": int(row["paperYear"]),
        "locator": row["locator"],
        "page": int(row["page"]),
    }


def _row_view(row: dict) -> dict:
    """One BenchmarkResult row shaped for narration: value + full citation."""
    view = {
        "method": row["method"],
        "method_label": row["methodLabel"],
        "dataset_label": row["datasetLabel"],
        "metric": row["metric"],
        "metric_label": row["metricLabel"],
        "value": float(row["value"]),
        "citation": _citation(row),
    }
    if "stdErr" in row:
        view["std_error"] = float(row["stdErr"])
    if "seen" in row:
        view["dataset_seen_by_model"] = row["seen"]
    return view


def _direction_word(direction_uri: str) -> str:
    if direction_uri == HIGHER:
        return "higher is better"
    if direction_uri == LOWER:
        return "lower is better"
    raise ValueError(f"unknown optimizationDirection: {direction_uri}")


def _best(rows: list, direction_uri: str) -> dict:
    """Best row per the metric's own direction (read from the graph)."""
    key = lambda r: float(r["value"])
    return max(rows, key=key) if direction_uri == HIGHER else min(rows, key=key)


def _ranked(rows: list, direction_uri: str) -> list:
    return sorted(rows, key=lambda r: float(r["value"]), reverse=direction_uri == HIGHER)


# ── compare_pair (flagship) ───────────────────────────────────────────────────

def _compare_sparql(slots: dict) -> str:
    return (
        PREFIXES
        + f"SELECT {_RESULT_VARS} WHERE {{\n"
        + f"  VALUES ?method {{ {_uri(slots, 'method_a')} {_uri(slots, 'method_b')} }}\n"
        + f"  VALUES ?dataset {{ {_uri(slots, 'dataset')} }}\n"
        + _metric_clause(slots)
        + _RESULT_BLOCK
        + "}\nORDER BY ?metricLabel ?methodLabel\n"
    )


def _compare_shape(rows: list, slots: dict) -> dict:
    a_uri, b_uri = slots["method_a"], slots["method_b"]
    by_metric: dict = {}
    for r in rows:
        by_metric.setdefault(r["metric"], []).append(r)

    comparisons, partial = [], []
    for metric_uri, mrows in sorted(by_metric.items()):
        a = [r for r in mrows if r["method"] == a_uri]
        b = [r for r in mrows if r["method"] == b_uri]
        if not a or not b:
            partial.extend(_row_view(r) for r in mrows)
            continue
        ra, rb = a[0], b[0]
        direction = ra["direction"]
        va, vb = float(ra["value"]), float(rb["value"])
        if va == vb:
            winner = None
        else:
            winner = _best([ra, rb], direction)
        comparisons.append({
            "metric": metric_uri,
            "metric_label": ra["metricLabel"],
            "direction": _direction_word(direction),
            "a": _row_view(ra),
            "b": _row_view(rb),
            "winner": None if winner is None else winner["method"],
            "winner_label": "tie" if winner is None else winner["methodLabel"],
            "margin": round(abs(va - vb), 6),
        })
    return {
        "kind": "compare_pair",
        "comparisons": comparisons,
        "one_sided": partial,  # rows where only one of the two methods has data
    }


# ── best_on_dataset ───────────────────────────────────────────────────────────

def _best_sparql(slots: dict) -> str:
    return (
        PREFIXES
        + f"SELECT {_RESULT_VARS} WHERE {{\n"
        + f"  VALUES ?dataset {{ {_uri(slots, 'dataset')} }}\n"
        + _metric_clause(slots)
        + _RESULT_BLOCK
        + "}\nORDER BY ?metricLabel ?value\n"
    )


def _best_shape(rows: list, slots: dict) -> dict:
    by_metric: dict = {}
    for r in rows:
        by_metric.setdefault(r["metric"], []).append(r)

    rankings = []
    for metric_uri, mrows in sorted(by_metric.items()):
        direction = mrows[0]["direction"]
        ordered = _ranked(mrows, direction)
        rankings.append({
            "metric": metric_uri,
            "metric_label": mrows[0]["metricLabel"],
            "direction": _direction_word(direction),
            "best": _row_view(ordered[0]),
            "ranking": [
                {"rank": i + 1, **_row_view(r)} for i, r in enumerate(ordered)
            ],
        })
    return {"kind": "best_on_dataset", "rankings": rankings}


# ── lookup_result ─────────────────────────────────────────────────────────────

def _lookup_sparql(slots: dict) -> str:
    return (
        PREFIXES
        + f"SELECT {_RESULT_VARS} WHERE {{\n"
        + f"  VALUES ?method {{ {_uri(slots, 'method')} }}\n"
        + f"  VALUES ?dataset {{ {_uri(slots, 'dataset')} }}\n"
        + _metric_clause(slots)
        + _RESULT_BLOCK
        + "}\nORDER BY ?metricLabel\n"
    )


def _lookup_shape(rows: list, slots: dict) -> dict:
    return {"kind": "lookup_result", "results": [_row_view(r) for r in rows]}


# ── seen_unseen (ADR-017 annotation aggregate) ────────────────────────────────

def _seen_unseen_sparql(slots: dict) -> str:
    # Every result on every (dataset, metric) where the target method carries a
    # :datasetSeenByModel annotation; ranks are computed in the shaper.
    return (
        PREFIXES
        + f"SELECT {_RESULT_VARS} ?targetSeen WHERE {{\n"
        + f"  ?targetResult a :BenchmarkResult ;\n"
        + f"          :reportsMethod {_uri(slots, 'method')} ;\n"
        + "          :onDataset ?dataset ;\n"
        + "          :usesMetric ?metric ;\n"
        + "          :datasetSeenByModel ?targetSeen .\n"
        + _RESULT_BLOCK
        + "}\nORDER BY ?datasetLabel ?value\n"
    )


def _seen_unseen_shape(rows: list, slots: dict) -> dict:
    target = slots["method"]
    by_key: dict = {}
    for r in rows:
        by_key.setdefault((r["dataset"], r["metric"]), []).append(r)

    per_dataset, buckets = [], {"seen": [], "unseen": []}
    for (_, _), krows in sorted(by_key.items(), key=lambda kv: kv[1][0]["datasetLabel"]):
        direction = krows[0]["direction"]
        ordered = _ranked(krows, direction)
        target_rank = next(
            (i + 1 for i, r in enumerate(ordered) if r["method"] == target), None
        )
        if target_rank is None:
            continue
        target_row = ordered[target_rank - 1]
        status = target_row["targetSeen"]
        entry = {
            "dataset_label": target_row["datasetLabel"],
            "metric_label": target_row["metricLabel"],
            "direction": _direction_word(direction),
            "status": status,
            "rank": target_rank,
            "of": len(ordered),
            "value": float(target_row["value"]),
            "citation": _citation(target_row),
        }
        per_dataset.append(entry)
        buckets.setdefault(status, []).append(target_rank)

    def _summary(ranks: list) -> dict:
        return {
            "n_datasets": len(ranks),
            "mean_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "wins": sum(1 for r in ranks if r == 1),
        }

    return {
        "kind": "seen_unseen",
        "method": target,
        "method_label": rows[0]["methodLabel"] if rows else None,
        "seen": _summary(buckets["seen"]),
        "unseen": _summary(buckets["unseen"]),
        "per_dataset": per_dataset,
        "note": "Ranks are within (dataset, metric) against all methods in the "
                "graph; direction per the metric's optimizationDirection.",
    }


# ── registry ──────────────────────────────────────────────────────────────────

@dataclass
class OperationSpec:
    name: str
    description: str          # shown to the planner LLM
    required_slots: dict      # slot name -> entity type
    optional_slots: dict
    build_sparql: callable    # slots -> SPARQL string
    shape: callable           # (rows, slots) -> narration payload


OPERATIONS = {
    op.name: op
    for op in [
        OperationSpec(
            name="compare_pair",
            description=(
                "Compare two methods on one dataset (optionally one metric). "
                "Answers 'did A beat B on D?' — the winner is derived from the "
                "metric's optimization direction."
            ),
            required_slots={"method_a": "Method", "method_b": "Method",
                            "dataset": "Dataset"},
            optional_slots={"metric": "Metric"},
            build_sparql=_compare_sparql,
            shape=_compare_shape,
        ),
        OperationSpec(
            name="best_on_dataset",
            description=(
                "Rank every method with a result on one dataset (optionally one "
                "metric). Answers 'which model was best on D?'."
            ),
            required_slots={"dataset": "Dataset"},
            optional_slots={"metric": "Metric"},
            build_sparql=_best_sparql,
            shape=_best_shape,
        ),
        OperationSpec(
            name="lookup_result",
            description=(
                "Fetch one method's reported value(s) on one dataset (optionally "
                "one metric). Answers 'what did M score on D?'."
            ),
            required_slots={"method": "Method", "dataset": "Dataset"},
            optional_slots={"metric": "Metric"},
            build_sparql=_lookup_sparql,
            shape=_lookup_shape,
        ),
        OperationSpec(
            name="seen_unseen",
            description=(
                "For one method, aggregate how it ranks on datasets it had 'seen' "
                "vs 'unseen' (the paper's own model-provenance annotation, "
                "ADR-017). Answers 'does M do better on datasets it was tuned on?'."
            ),
            required_slots={"method": "Method"},
            optional_slots={},
            build_sparql=_seen_unseen_sparql,
            shape=_seen_unseen_shape,
        ),
    ]
}


def operations_prompt_block() -> str:
    lines = []
    for op in OPERATIONS.values():
        req = ", ".join(f"{k}: {v}" for k, v in op.required_slots.items())
        opt = ", ".join(f"{k}: {v} (optional)" for k, v in op.optional_slots.items())
        slots = "; ".join(x for x in (req, opt) if x)
        lines.append(f"- {op.name} [{slots}] — {op.description}")
    return "\n".join(lines)
