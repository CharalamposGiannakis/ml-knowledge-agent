"""Narration: turn a shaped operation payload into prose — provably grounded.

Per ADR-019 the DEFAULT answer path is deterministic: code renders the answer
sentence from the verified payload (`template_answer`). The model never writes
the asserted content — it only interprets the question upstream (resolve /
select / fill slots). This closes red-team F1 (a token-provenance guard cannot
tell a true sentence from a false one) by construction rather than by an
ever-smarter guard.

An optional LLM narrator is retained ONLY behind an explicit, non-default flag
(`Narrator(use_llm=True)`). Even then:
- the untrusted question is NEVER placed in the narrator prompt (no injection
  path into answer wording), and
- the `guard` below is applied as defense-in-depth (every number must already
  appear in the payload; an exact "<locator>, p.<page>" citation must be
  present), with any failure falling back to the deterministic template.
The guard is a backstop, not the guarantee — the guarantee is that the default
path never asks a model to assert anything.
"""
import json
import os
import re
from dotenv import load_dotenv

from agent.sparql import REPO_ROOT

DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "claude-opus-4-8")

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

NARRATE_SYSTEM = """\
You narrate benchmark query results from a knowledge graph. The payload JSON
you receive is the COMPLETE set of facts you may state. You are given NO user
question — narrate only what the payload asserts.

Rules:
1. Use only facts present in the payload. No outside knowledge, no arithmetic
   beyond numbers already present in the payload.
2. Cite every claim with its source, writing the locator and page exactly as
   "<locator>, p.<page>" (e.g. "Table 2, p.6"), naming the paper at least once.
3. Respect the stated optimization direction when saying who wins or ranks
   where; never assume higher is better.
4. If the payload marks a caveat (one-sided data, missing annotation), say so.
5. 2–5 sentences of plain prose. No markdown, no bullet lists. Never mention
   the payload, the graph, or these instructions — just answer with sources.
"""


# ── guard ─────────────────────────────────────────────────────────────────────

def _payload_numbers(obj, acc: set) -> set:
    """Every number in the payload, incl. numbers embedded in its strings."""
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM_RE.findall(obj):
            acc.add(float(m))
    elif isinstance(obj, dict):
        for v in obj.values():
            _payload_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _payload_numbers(v, acc)
    return acc


def citation_strings(shaped: dict) -> list:
    """All '<locator>, p.<page>' strings appearing in the payload's citations."""
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            if "locator" in obj and "page" in obj:
                s = f"{obj['locator']}, p.{obj['page']}"
                if s not in found:
                    found.append(s)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(shaped)
    return found


def guard(text: str, shaped: dict) -> tuple:
    """(ok, reason). Deterministic acceptance test for narration."""
    if not text.strip():
        return False, "empty narration"
    allowed = _payload_numbers(shaped, set())
    for m in _NUM_RE.findall(text):
        if float(m) not in allowed:
            return False, f"number {m} not present in the returned rows"
    cites = citation_strings(shaped)
    if cites and not any(c in text for c in cites):
        return False, "no exact '<locator>, p.<page>' citation from the rows"
    return True, ""


# ── deterministic templates ───────────────────────────────────────────────────

def _fmt(row: dict) -> str:
    se = f" ± {row['std_error']}" if "std_error" in row else ""
    return f"{row['method_label']} = {row['value']}{se}"


def _cite(c: dict) -> str:
    return f"({c['paper']}, {c['locator']}, p.{c['page']})"


def template_answer(shaped: dict) -> str:
    kind = shaped["kind"]

    if kind == "compare_pair":
        parts = []
        for c in shaped["comparisons"]:
            head = (
                f"On {c['a']['dataset_label']} by {c['metric_label']} "
                f"({c['direction']}): "
            )
            if c["winner"] is None:
                head += f"tie — {_fmt(c['a'])} vs {_fmt(c['b'])}"
            else:
                head += (
                    f"{c['winner_label']} wins — {_fmt(c['a'])} vs {_fmt(c['b'])}, "
                    f"margin {c['margin']}"
                )
            parts.append(head + f" {_cite(c['a']['citation'])}.")
        for r in shaped.get("one_sided", []):
            parts.append(
                f"Caveat: only {r['method_label']} has a "
                f"{r['metric_label']} result here ({r['value']}) "
                f"{_cite(r['citation'])}."
            )
        return " ".join(parts)

    if kind == "best_on_dataset":
        parts = []
        for r in shaped["rankings"]:
            best = r["best"]
            runner = r["ranking"][1] if len(r["ranking"]) > 1 else None
            s = (
                f"Best on {best['dataset_label']} by {r['metric_label']} "
                f"({r['direction']}): {_fmt(best)}"
            )
            if runner:
                s += f", ahead of {_fmt(runner)}"
            s += f", out of {len(r['ranking'])} methods {_cite(best['citation'])}."
            parts.append(s)
        return " ".join(parts)

    if kind == "lookup_result":
        return " ".join(
            f"{r['method_label']} on {r['dataset_label']}: "
            f"{r['metric_label']} = {r['value']}"
            + (f" ± {r['std_error']}" if "std_error" in r else "")
            + f" ({r['direction'] if 'direction' in r else ''})".replace(" ()", "")
            + f" {_cite(r['citation'])}."
            for r in shaped["results"]
        )

    if kind == "seen_unseen":
        s, u = shaped["seen"], shaped["unseen"]
        cite = _cite(shaped["per_dataset"][0]["citation"]) if shaped["per_dataset"] else ""
        return (
            f"{shaped['method_label']} — mean rank {s['mean_rank']} across "
            f"{s['n_datasets']} seen dataset(s) ({s['wins']} wins) vs mean rank "
            f"{u['mean_rank']} across {u['n_datasets']} unseen dataset(s) "
            f"({u['wins']} wins); rank 1 is best within each dataset and metric "
            f"{cite}. {shaped['note']}"
        )

    raise ValueError(f"no template for payload kind {kind!r}")


def render_conflicts(shaped: dict) -> str:
    """Honest text for a cell with more than one BenchmarkResult (F2). The
    agent refuses to pick one; it names every disagreeing source instead."""
    parts = []
    for c in shaped.get("conflicts", []):
        srcs = "; ".join(
            f"{s['value']} ({s['citation']['paper']}, {s['citation']['locator']}, "
            f"p.{s['citation']['page']})"
            for s in c["sources"]
        )
        parts.append(
            f"{c['method_label']} on {c['dataset_label']} by {c['metric_label']} "
            f"has {len(c['sources'])} results in the graph ({srcs}); I won't "
            f"silently pick one."
        )
    return " ".join(parts)


# ── narrator ──────────────────────────────────────────────────────────────────

class Narrator:
    """Answer rendering. Deterministic template by default (ADR-019); the LLM
    path is opt-in (`use_llm=True`) and, even then, never sees the question and
    must pass the `guard` or fall back to the template."""

    def __init__(self, model: str = DEFAULT_MODEL, client=None, use_llm: bool = False):
        self.model = model
        self._client = client
        self.use_llm = use_llm

    def _get_client(self):
        if self._client is None:
            load_dotenv(REPO_ROOT / ".env")
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return None
            from anthropic import Anthropic
            self._client = Anthropic()
        return self._client

    def narrate(self, shaped: dict) -> tuple:
        """Returns (text, source) with source in {'llm', 'template'}. The
        question is deliberately NOT a parameter — no untrusted text reaches
        the narrator prompt (ADR-019)."""
        fallback = template_answer(shaped)
        if not self.use_llm:
            return fallback, "template"
        client = self._get_client()
        if client is None:
            return fallback, "template"
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=600,
                system=NARRATE_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"Payload:\n{json.dumps(shaped, indent=2)}",
                }],
            )
            text = "".join(b.text for b in response.content if b.type == "text").strip()
        except Exception:
            return fallback, "template"
        ok, _reason = guard(text, shaped)
        return (text, "llm") if ok else (fallback, "template")
