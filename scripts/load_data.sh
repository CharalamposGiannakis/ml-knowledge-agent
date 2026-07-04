#!/usr/bin/env bash
# Generic data loader: POST a reviewed .ttl into the mlkg dataset's default graph.
# Runs the SHACL gate first; refuses to POST if the file does not conform.
# Usage: bash scripts/load_data.sh data/shwartzziv2022.ttl
set -euo pipefail
FILE="${1:?usage: load_data.sh <file.ttl>}"
FUSEKI_URL="${FUSEKI_URL:-http://localhost:3030}"
DATASET="${DATASET:-mlkg}"
ADMIN_USER="${FUSEKI_ADMIN_USER:-admin}"

if [ -z "${FUSEKI_ADMIN_PASSWORD:-}" ]; then
  echo "ERROR: FUSEKI_ADMIN_PASSWORD is not set. Copy .env.example to .env and set a real password." >&2
  exit 1
fi
ADMIN_PW="${FUSEKI_ADMIN_PASSWORD}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Single bounded reachability check — not a retry loop. If Fuseki is mid
# restart-loop (see init_fuseki.sh) this fails fast instead of handing curl's
# connection-refused error straight to the user.
if ! curl -fsS -m 5 "${FUSEKI_URL}/\$/ping" >/dev/null 2>&1; then
  echo "UNREACHABLE: Fuseki did not respond at ${FUSEKI_URL} — is 'docker compose up -d' running?" >&2
  exit 1
fi

echo "==> SHACL gate: validating ${FILE} ..."
python3 "${SCRIPT_DIR}/validate_shapes.py" "${FILE}"

echo "==> Loading ${FILE} into ${DATASET} ..."
status="$(curl -sS -o /dev/null -w '%{http_code}' -u "${ADMIN_USER}:${ADMIN_PW}" \
     -X POST -H "Content-Type: text/turtle" \
     --data-binary "@${FILE}" \
     "${FUSEKI_URL}/${DATASET}/data?default")"
case "${status}" in
  200|201)
    echo "    loaded."
    ;;
  401)
    echo "ERROR: HTTP 401 Unauthorized loading ${FILE}." >&2
    echo "  FUSEKI_ADMIN_PASSWORD does not match the container's admin password. Not retrying." >&2
    exit 1
    ;;
  404)
    echo "ERROR: HTTP 404 — dataset '${DATASET}' does not exist yet." >&2
    echo "  Run: bash scripts/init_fuseki.sh" >&2
    exit 1
    ;;
  *)
    echo "ERROR: unexpected HTTP ${status} loading ${FILE}." >&2
    exit 1
    ;;
esac

echo "==> BenchmarkResults now in graph:"
curl -fsS "${FUSEKI_URL}/${DATASET}/query" \
  --data-urlencode 'query=PREFIX : <http://mlkg.local/ontology#> SELECT (COUNT(?r) AS ?n) WHERE { ?r a :BenchmarkResult }' \
  -H "Accept: text/csv"
