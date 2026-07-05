"""CLI for the query agent.

Usage:
    python -m agent "Did XGBoost beat TabNet on Gesture?"
    python -m agent --json "Which model was best on Rossmann?"
    python -m agent --explain "..."

Answers are rendered deterministically from the verified payload (ADR-019); the
LLM never writes the answer sentence. `--llm-narration` opts into experimental
LLM phrasing (guarded, and never shown the question) — off by default.

Requires Fuseki up (docker compose up -d) and ANTHROPIC_API_KEY in .env for
the planner. SELECTs are sent anonymously (ADR-016).
"""
import argparse
import json
import sys

from agent.catalog import Catalog
from agent.loop import answer_question
from agent.narrator import Narrator
from agent.sparql import FusekiBackend


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # '±' on Windows consoles
    parser = argparse.ArgumentParser(
        prog="agent", description="Ask the ML knowledge graph a question."
    )
    parser.add_argument("question", help="natural-language benchmark question")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the full structured Answer as JSON")
    parser.add_argument("--llm-narration", action="store_true",
                        help="opt into experimental guarded LLM phrasing "
                             "(default: deterministic template, ADR-019)")
    parser.add_argument("--no-llm-narration", action="store_true",
                        help=argparse.SUPPRESS)  # deprecated: now the default
    parser.add_argument("--explain", action="store_true",
                        help="also print operation, slots, and citations")
    args = parser.parse_args(argv)

    backend = FusekiBackend()
    try:
        catalog = Catalog.fetch(backend)
    except Exception as exc:
        print(f"Cannot reach Fuseki ({exc}). Run: docker compose up -d",
              file=sys.stderr)
        return 2

    answer = answer_question(
        args.question,
        backend=backend,
        catalog=catalog,
        narrator=Narrator(use_llm=args.llm_narration),
    )

    if args.as_json:
        print(json.dumps(answer.to_dict(), indent=2))
        return 0 if answer.status != "error" else 1

    print(f"[{answer.status}] {answer.text}")
    if args.explain:
        print(f"\noperation : {answer.operation or '-'}")
        print(f"slots     : {answer.slots}")
        print(f"narration : {answer.narration_source or '-'}")
        for c in answer.citations:
            print(f"citation  : {c}")
    return 0 if answer.status != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
