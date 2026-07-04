"""Thin FastAPI route over the same agent loop as the CLI.

Run:
    uvicorn agent.api:app --port 8000
    curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "Did XGBoost beat TabNet on Gesture?"}'

The route holds no write credentials and reuses answer_question unchanged —
one loop, two frontends. The catalog is fetched once per process and reused;
restart (or POST /refresh-catalog) after loading new data.
"""
from fastapi import FastAPI
from pydantic import BaseModel

from agent.catalog import Catalog
from agent.loop import answer_question
from agent.sparql import FusekiBackend

app = FastAPI(
    title="MLKG query agent",
    description="Natural-language benchmark questions -> sourced answers "
                "from the RDF knowledge graph (ADR-018).",
)

_state: dict = {}


def _get_catalog_and_backend():
    if "backend" not in _state:
        _state["backend"] = FusekiBackend()
        _state["catalog"] = Catalog.fetch(_state["backend"])
    return _state["catalog"], _state["backend"]


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    catalog, backend = _get_catalog_and_backend()
    answer = answer_question(req.question, backend=backend, catalog=catalog)
    return answer.to_dict()


@app.post("/refresh-catalog")
def refresh_catalog() -> dict:
    _state.clear()
    catalog, _ = _get_catalog_and_backend()
    return {"entities": len(catalog.entities)}


@app.get("/health")
def health() -> dict:
    catalog, _ = _get_catalog_and_backend()
    return {"status": "ok", "catalog_entities": len(catalog.entities)}
