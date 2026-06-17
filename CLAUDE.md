# CLAUDE.md — Working notes for Claude Code

> Read this before doing anything in this repo. The full reasoning lives in `docs/DESIGN.md`
> and `docs/DECISIONS.md`; this file is the short operational version.

## What this project is
A personal ML-Engineering research agent over a curated **RDF/SPARQL knowledge graph**. You ask a
natural-language question; the agent queries the graph and answers with an exact source (paper,
table/figure, page). If the graph lacks the answer, it says so. No fabrication.

## Non-negotiable rules
1. **No triple enters the graph without (a) a source location and (b) passing human review.**
   Never auto-commit extracted triples to Fuseki.
2. **The atom is `BenchmarkResult`, not a comparison.** Comparisons are derived in SPARQL at query
   time. Do not add a `Comparison` class.
3. **Always-working-slice.** Never leave the repo in a state with no runnable end-to-end path.
   Prefer a thin slice over broad half-built infra.
4. **Source of truth is `docs/DESIGN.md`.** If you change architecture, update DESIGN.md and add an
   ADR to `docs/DECISIONS.md` in the same change.
5. **Required core fields** for any result: method, dataset, metric, value, source. Conditions are
   accept-and-flag if partial — never silently drop them, never hard-reject for being incomplete.

## Model usage
- Design, ontology, extraction-prompt work, runtime extraction → **Opus 4.8**.
- Boilerplate, tests-from-spec, mechanical refactors → **Sonnet**.

## Conventions
- Python: FastAPI backend, PyMuPDF for PDFs, ChromaDB for vectors.
- Keep the repo free of empty folders. Add a folder only when there's code to put in it.
- Each session: update `STATUS.md` (Done / In progress / Next actions) before stopping.

## How to run
- Fuseki: (fill in once Phase 0 is set up)
- Backend: (fill in)
- Frontend: (fill in)
