#!/usr/bin/env python3
"""Eval runner: question -> expected outcome + expected source (ADR-006).

Runs every item in eval/eval_set.jsonl through the real agent loop (live
Fuseki + live LLM planner; deterministic template narration, since scoring is
on the structured Answer, not prose) and reports:

- retrieval accuracy: status + winner/value/rank expectations matched
- citation accuracy: expected locator+page present in the answer's citations
  (over items that expect an answered status with a source)

Usage:
    python eval/run_eval.py            # all items
    python eval/run_eval.py --id sz2022-gesture-xgb-vs-tabnet

Exit code 0 iff every item passes both checks.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agent.catalog import Catalog
from agent.loop import answer_question
from agent.narrator import Narrator
from agent.sparql import FusekiBackend

EVAL_SET = Path(__file__).parent / "eval_set.jsonl"


def _local(uri: str) -> str:
    return uri.split("#")[-1] if uri else ""


def _winners(shaped: dict) -> set:
    if shaped.get("kind") == "compare_pair":
        return {_local(c["winner"]) for c in shaped["comparisons"] if c["winner"]}
    if shaped.get("kind") == "best_on_dataset":
        return {_local(r["best"]["method"]) for r in shaped["rankings"]}
    return set()


def _values(obj, acc: list) -> list:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "value" and isinstance(v, (int, float)):
                acc.append(float(v))
            else:
                _values(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _values(v, acc)
    return acc


def check_retrieval(answer, expect: dict) -> list:
    """Returns the list of failed expectations (empty = pass)."""
    fails = []
    want_status = expect.get("status", "answered")
    if answer.status != want_status:
        fails.append(f"status={answer.status!r}, want {want_status!r}")
        return fails  # downstream checks meaningless on wrong status
    if want_status != "answered":
        return fails

    if "operation" in expect and answer.operation != expect["operation"]:
        fails.append(f"operation={answer.operation!r}, want {expect['operation']!r}")
    if "winner" in expect:
        want = expect["winner"].lstrip(":")
        got = _winners(answer.shaped)
        if want not in got:
            fails.append(f"winner {want!r} not in {sorted(got) or ['<none>']}")
    if "value" in expect:
        got = _values(answer.shaped, [])
        if not any(abs(v - expect["value"]) < 1e-6 for v in got):
            fails.append(f"value {expect['value']} not among returned values")
    for key, path in (("seen_mean_rank", "seen"), ("unseen_mean_rank", "unseen")):
        if key in expect:
            got = (answer.shaped.get(path) or {}).get("mean_rank")
            if got is None or abs(got - expect[key]) > 0.01:
                fails.append(f"{key}={got}, want {expect[key]}")
    return fails


def check_citation(answer, expected_source: dict) -> list:
    want = f"{expected_source['locator']}, p.{expected_source['page']}"
    if want not in answer.citations:
        return [f"citation {want!r} not in {answer.citations}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the agent eval set.")
    parser.add_argument("--id", help="run a single eval item by id")
    args = parser.parse_args()

    items = [json.loads(line) for line in
             EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.id:
        items = [i for i in items if i["id"] == args.id]
        if not items:
            sys.exit(f"no eval item with id {args.id!r}")

    backend = FusekiBackend()
    catalog = Catalog.fetch(backend)
    narrator = Narrator(use_llm=False)  # scoring is structural, not prose

    retrieval_pass = citation_pass = citation_total = 0
    failures = []

    for item in items:
        answer = answer_question(item["question"], backend=backend,
                                 catalog=catalog, narrator=narrator)
        r_fails = check_retrieval(answer, item.get("expect", {}))

        c_fails = []
        if item.get("expect", {}).get("status", "answered") == "answered" \
                and "expected_source" in item:
            citation_total += 1
            if answer.status == "answered" or answer.citations:
                c_fails = check_citation(answer, item["expected_source"])
            else:
                c_fails = ["no citations returned"]
            if not c_fails:
                citation_pass += 1

        if not r_fails:
            retrieval_pass += 1
        ok = not r_fails and not c_fails
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {item['id']}  ({answer.status}/{answer.operation or '-'})")
        for f in r_fails + c_fails:
            print(f"       - {f}")
        if not ok:
            failures.append(item["id"])

    n = len(items)
    print("\n" + "=" * 60)
    print(f"retrieval accuracy : {retrieval_pass}/{n} "
          f"({100 * retrieval_pass / n:.0f}%)")
    if citation_total:
        print(f"citation accuracy  : {citation_pass}/{citation_total} "
              f"({100 * citation_pass / citation_total:.0f}%)")
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("all eval items passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
