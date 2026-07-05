"""LLM planner: question -> (operation choice, slot URIs) — never SPARQL.

The model sees the entity catalog (labels + SKOS aliases with their URIs) and
the operation library descriptions, and must answer through a forced tool call
whose schema only admits: an operation name, slot fills, ambiguity reports,
and unresolved terms. Whatever it returns is re-validated by the loop against
the catalog before any query is built (ADR-018).
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from agent.operations import OPERATIONS, operations_prompt_block
from agent.sparql import REPO_ROOT

DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "claude-opus-4-8")

PLAN_TOOL = {
    "name": "submit_plan",
    "description": "Submit the query plan for the user's question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": sorted(OPERATIONS) + ["unsupported"],
                "description": "Chosen operation, or 'unsupported' if no "
                               "operation can express the question.",
            },
            "slots": {
                "type": "object",
                "description": "Slot name -> exact entity URI copied from the "
                               "catalog. Only slots the operation defines.",
                "additionalProperties": {"type": "string"},
            },
            "slot_terms": {
                "type": "object",
                "description": "Slot name -> the exact word/phrase from the "
                               "QUESTION that you matched to fill that slot "
                               "(the surface term, e.g. 'XGB' or 'Gesture "
                               "Phase'). Code re-checks each against the "
                               "catalog, so give one for every filled slot.",
                "additionalProperties": {"type": "string"},
            },
            "ambiguities": {
                "type": "array",
                "description": "Question terms that match MORE THAN ONE "
                               "catalog entity of the needed type.",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "candidates": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Candidate entity URIs from the catalog.",
                        },
                    },
                    "required": ["term", "candidates"],
                },
            },
            "unresolved_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Question terms needed for a slot that match "
                               "NO catalog label or alias.",
            },
            "note": {
                "type": "string",
                "description": "One sentence: why unsupported / what is "
                               "ambiguous or unresolved. Empty if clean.",
            },
        },
        "required": ["operation"],
    },
}

SYSTEM_PROMPT = """\
You are the query planner for a benchmark knowledge graph. You NEVER write
SPARQL or invent facts. Your only job: map the user's question onto ONE
operation from the library below and fill its slots with entity URIs copied
EXACTLY from the catalog.

Rules:
1. Match question terms against catalog labels and aliases (case-insensitive,
   ignore trivial punctuation). Use ONLY URIs that appear in the catalog.
2. A term that matches nothing goes in unresolved_terms — do not guess a
   nearest entity.
3. A term that matches more than one entity of the needed type goes in
   ambiguities with all candidate URIs — do not pick one silently.
4. 'unsupported' is ONLY for question SHAPES the library cannot express
   (causal 'why', cross-dataset averages, ...). If the shape fits an
   operation but an entity is unknown, still choose that operation and
   report the term in unresolved_terms — never 'unsupported'.
5. Only fill the 'metric' slot if the question names a metric; otherwise leave
   it out and the operation covers all metrics on that dataset.
6. For every slot you fill, also record in slot_terms the exact surface term
   from the question that you matched (the label or alias, not a paraphrase).
   Code re-derives resolution from it, so a term that doesn't match the URI you
   chose will be rejected.
7. Always answer via the submit_plan tool.

Operations:
{operations}

Catalog:
{catalog}
"""


@dataclass
class Plan:
    operation: str
    slots: dict = field(default_factory=dict)
    slot_terms: dict = field(default_factory=dict)
    ambiguities: list = field(default_factory=list)
    unresolved_terms: list = field(default_factory=list)
    note: str = ""


class LLMPlanner:
    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client

    @property
    def client(self):
        if self._client is None:
            load_dotenv(REPO_ROOT / ".env")
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set (add it to .env). The planner "
                    "needs it; SPARQL execution itself never does."
                )
            from anthropic import Anthropic
            self._client = Anthropic()
        return self._client

    def plan(self, question: str, catalog) -> Plan:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(
                operations=operations_prompt_block(),
                catalog=catalog.prompt_block(),
            ),
            tools=[PLAN_TOOL],
            tool_choice={"type": "tool", "name": "submit_plan"},
            messages=[{"role": "user", "content": question}],
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        p = tool_use.input
        return Plan(
            operation=p.get("operation", "unsupported"),
            slots=p.get("slots") or {},
            slot_terms=p.get("slot_terms") or {},
            ambiguities=p.get("ambiguities") or [],
            unresolved_terms=p.get("unresolved_terms") or [],
            note=p.get("note") or "",
        )
