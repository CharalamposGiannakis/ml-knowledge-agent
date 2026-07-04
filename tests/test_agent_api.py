"""Smoke test for the FastAPI route: wiring + serialization only.

The loop itself is covered by test_query_agent.py; here answer_question is
stubbed so the test needs neither Fuseki nor an API key.
"""
from fastapi.testclient import TestClient

import agent.api as api
from agent.loop import Answer


def test_ask_route_serializes_answer(monkeypatch):
    def fake_answer(question, backend=None, catalog=None, **kwargs):
        return Answer(
            status="answered", question=question,
            text="XGBoost wins (Table 2, p.6).",
            operation="compare_pair",
            citations=["Table 2, p.6"], narration_source="template",
        )

    monkeypatch.setattr(api, "answer_question", fake_answer)
    monkeypatch.setattr(api, "_get_catalog_and_backend", lambda: (None, None))

    client = TestClient(api.app)
    resp = client.post("/ask", json={"question": "Did XGBoost beat TabNet?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert body["question"] == "Did XGBoost beat TabNet?"
    assert body["citations"] == ["Table 2, p.6"]
