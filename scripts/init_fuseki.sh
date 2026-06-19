#!/usr/bin/env bash
# Close the Phase 0 slice: ensure the dataset exists, load the ontology, run a live query.
# Idempotent — safe to re-run. Talks to Fuseki over standard HTTP, so it is image-agnostic.
set -euo pipefail

if [ -z "${FUSEKI_ADMIN_PASSWORD:-}" ]; then
  echo "ERROR: FUSEKI_ADMIN_PASSWORD is not set. Copy .env.example to .env and set a real password before running make init." >&2
  exit 1
fi

FUSEKI_URL="${FUSEKI_URL:-http://localhost:3030}"
DATASET="${DATASET:-mlkg}"
ADMIN_USER="${FUSEKI_ADMIN_USER:-admin}"
ADMIN_PW="${FUSEKI_ADMIN_PASSWORD}"
ONTOLOGY="${ONTOLOGY:-ontology/mlkg.ttl}"

PING_URL="${FUSEKI_URL}/\$/ping"
DS_ADMIN_URL="${FUSEKI_URL}/\$/datasets"

echo "==> Waiting for Fuseki at ${FUSEKI_URL} ..."
for i in $(seq 1 30); do
  if curl -fsS "${PING_URL}" >/dev/null 2>&1; then
    echo "    up."
    break
  fi
  if [ "${i}" -eq 30 ]; then
    echo "    timed out waiting for Fuseki (is 'docker compose up -d' running?)." >&2
    exit 1
  fi
  sleep 1
done

echo "==> Ensuring dataset '${DATASET}' exists ..."
if curl -fsS -u "${ADMIN_USER}:${ADMIN_PW}" "${DS_ADMIN_URL}/${DATASET}" >/dev/null 2>&1; then
  echo "    already present."
else
  curl -fsS -u "${ADMIN_USER}:${ADMIN_PW}" \
       -d "dbName=${DATASET}&dbType=tdb2" \
       "${DS_ADMIN_URL}" >/dev/null
  echo "    created (persistent TDB2)."
fi

echo "==> Loading ontology '${ONTOLOGY}' into the default graph ..."
curl -fsS -u "${ADMIN_USER}:${ADMIN_PW}" \
     -X POST -H "Content-Type: text/turtle" \
     --data-binary "@${ONTOLOGY}" \
     "${FUSEKI_URL}/${DATASET}/data?default" >/dev/null
echo "    loaded."

echo
echo "==> Smoke query — metrics and their optimization direction (expect 8 rows):"
curl -fsS "${FUSEKI_URL}/${DATASET}/query" \
  --data-urlencode 'query=PREFIX : <http://mlkg.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?metric ?direction WHERE {
  ?m a :Metric ; rdfs:label ?metric ; :optimizationDirection ?d .
  BIND(REPLACE(STR(?d), ".*#", "") AS ?direction)
} ORDER BY ?metric' \
  -H "Accept: text/csv"

echo
echo "==> Phase 0 slice CLOSED: Fuseki up, ontology loaded, live SPARQL answered."
