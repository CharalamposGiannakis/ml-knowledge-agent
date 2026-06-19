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
   ADR to `docs/DECISIONS.md` in the same change. The schema's source of truth is `ontology/mlkg.ttl`.
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
Prereqs: Docker + Docker Compose. (No host Java needed — the image bundles it.)

    cp .env.example .env                              # set FUSEKI_ADMIN_PASSWORD (once)
    source .env                                       # export vars into current shell
    docker compose up -d                              # start Fuseki at http://localhost:3030
    bash scripts/init_fuseki.sh                       # create dataset 'mlkg', load ontology, smoke query
    bash scripts/load_data.sh data/<reviewed>.ttl     # load a reviewed .ttl (repeat per file)
    python3 scripts/query.py < some.rq                # run an ad-hoc SPARQL SELECT

**Note:** `make init` will fail loudly if `FUSEKI_ADMIN_PASSWORD` is not set in `.env` — this is
intentional. Copy `.env.example` to `.env` and set a real password first.

- Fuseki UI:        http://localhost:3030  (user: admin, pw: from .env)
- Query endpoint:   http://localhost:3030/mlkg/query
- Update endpoint:  http://localhost:3030/mlkg/update
- GSP data load:    POST text/turtle to http://localhost:3030/mlkg/data?default
- Data persists in the `fuseki-data` volume. `docker compose down -v` wipes it.

If `docker compose up` fails on the image tag, verify a current tag on Docker Hub (Jena is on 5.x)
and update `docker-compose.yml`. The scripts talk to Fuseki over standard HTTP, so they are
image-agnostic once the server is reachable.
