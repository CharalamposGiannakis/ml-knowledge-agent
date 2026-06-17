.PHONY: help up down init query logs reset

help:           ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

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
