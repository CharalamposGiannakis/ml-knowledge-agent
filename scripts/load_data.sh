#!/usr/bin/env bash
# Generic data loader: POST a reviewed .ttl into the mlkg dataset's default graph.
# Runs the SHACL gate first; refuses to POST if the file does not conform.
# Usage: bash scripts/load_data.sh data/shwartzziv2022.ttl
set -euo pipefail
FILE="${1:?usage: load_data.sh <file.ttl>}"
FUSEKI_URL="${FUSEKI_URL:-http://localhost:3030}"
DATASET="${DATASET:-mlkg}"
ADMIN_USER="${FUSEKI_ADMIN_USER:-admin}"
ADMIN_PW="${FUSEKI_ADMIN_PASSWORD:-admin}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> SHACL gate: validating ${FILE} ..."
python3 "${SCRIPT_DIR}/validate_shapes.py" "${FILE}"

echo "==> Loading ${FILE} into ${DATASET} ..."
curl -fsS -u "${ADMIN_USER}:${ADMIN_PW}" \
     -X POST -H "Content-Type: text/turtle" \
     --data-binary "@${FILE}" \
     "${FUSEKI_URL}/${DATASET}/data?default" >/dev/null
echo "    loaded."

echo "==> BenchmarkResults now in graph:"
curl -fsS "${FUSEKI_URL}/${DATASET}/query" \
  --data-urlencode 'query=PREFIX : <http://mlkg.local/ontology#> SELECT (COUNT(?r) AS ?n) WHERE { ?r a :BenchmarkResult }' \
  -H "Accept: text/csv"
