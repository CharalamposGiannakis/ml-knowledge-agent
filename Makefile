.PHONY: help up down init query logs reset validate load-data healthcheck

help:           ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up:             ## start Fuseki (http://localhost:3030)
	docker compose up -d

down:           ## stop Fuseki (data persists in the named volume)
	docker compose down

init:           ## create dataset + load ontology + smoke query  (closes Phase 0)
	bash scripts/init_fuseki.sh

query:          ## run a SPARQL SELECT from stdin, e.g. `make query < q.rq`
	python3 scripts/query.py

logs:           ## tail Fuseki logs
	docker compose logs -f fuseki

reset:          ## DESTROY the volume and start clean (wipes all loaded data)
	docker compose down -v

validate:       ## SHACL gate: validate FILE against shapes (e.g. make validate FILE=data/foo.ttl)
	@test -n "$(FILE)" || (echo "usage: make validate FILE=data/foo.ttl" >&2 && exit 1)
	python3 scripts/validate_shapes.py $(FILE)

load-data: validate  ## SHACL gate + Fuseki POST (e.g. make load-data FILE=data/foo.ttl)
	bash scripts/load_data.sh $(FILE)

healthcheck:    ## Layer-2/3 SPARQL invariant checks against live Fuseki (ADR-015)
	python3 scripts/healthcheck.py
