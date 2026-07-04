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

# Bounded wait for connection-refused / not-up-yet. This is the ONLY retry
# loop in this script — it waits for the process to exist, never for auth to
# become correct. A container stuck restarting (e.g. incompatible TDB2 data
# under a mismatched Jena version on a reused volume) times out here with a
# clear message instead of looping forever.
echo "==> Waiting for Fuseki at ${FUSEKI_URL} ..."
for i in $(seq 1 30); do
  if curl -fsS -m 3 "${PING_URL}" >/dev/null 2>&1; then
    echo "    up."
    break
  fi
  if [ "${i}" -eq 30 ]; then
    echo "UNREACHABLE: Fuseki did not come up at ${FUSEKI_URL} after 30s." >&2
    echo "  Check 'docker compose ps' / 'docker compose logs fuseki' — a restart loop" >&2
    echo "  there usually means the data volume is incompatible with the image" >&2
    echo "  (e.g. after changing the Fuseki image version). A clean reset is safe;" >&2
    echo "  data reloads from .ttl: docker compose down -v && docker compose up -d." >&2
    exit 1
  fi
  sleep 1
done

# From here on, failures are classified by HTTP status, not by curl's blanket
# success/fail exit code — 401 (bad password) and 404 (dataset missing) need
# different fixes and neither should be retried.
echo "==> Ensuring dataset '${DATASET}' exists ..."
status="$(curl -sS -o /dev/null -w '%{http_code}' -u "${ADMIN_USER}:${ADMIN_PW}" "${DS_ADMIN_URL}/${DATASET}")"
case "${status}" in
  200)
    echo "    already present."
    ;;
  404)
    echo "    not found — creating (persistent TDB2) ..."
    create_status="$(curl -sS -o /dev/null -w '%{http_code}' -u "${ADMIN_USER}:${ADMIN_PW}" \
         -d "dbName=${DATASET}&dbType=tdb2" \
         "${DS_ADMIN_URL}")"
    if [ "${create_status}" != "200" ] && [ "${create_status}" != "201" ]; then
      echo "ERROR: dataset creation failed (HTTP ${create_status})." >&2
      exit 1
    fi
    echo "    created."
    ;;
  401)
    echo "ERROR: HTTP 401 Unauthorized checking dataset '${DATASET}'." >&2
    echo "  FUSEKI_ADMIN_PASSWORD does not match the container's admin password. Not retrying." >&2
    echo "  Fix: confirm .env matches what the container was started with, or recreate the" >&2
    echo "  container with the current .env: docker compose down && docker compose up -d." >&2
    exit 1
    ;;
  *)
    echo "ERROR: unexpected HTTP ${status} from ${DS_ADMIN_URL}/${DATASET}." >&2
    exit 1
    ;;
esac

echo "==> Loading ontology '${ONTOLOGY}' into the default graph ..."
load_status="$(curl -sS -o /dev/null -w '%{http_code}' -u "${ADMIN_USER}:${ADMIN_PW}" \
     -X POST -H "Content-Type: text/turtle" \
     --data-binary "@${ONTOLOGY}" \
     "${FUSEKI_URL}/${DATASET}/data?default")"
case "${load_status}" in
  200|201)
    echo "    loaded."
    ;;
  401)
    echo "ERROR: HTTP 401 Unauthorized loading ${ONTOLOGY}." >&2
    echo "  FUSEKI_ADMIN_PASSWORD does not match the container's admin password. Not retrying." >&2
    exit 1
    ;;
  *)
    echo "ERROR: unexpected HTTP ${load_status} loading ${ONTOLOGY}." >&2
    exit 1
    ;;
esac

echo
echo "==> Smoke query — metrics and their optimization direction (expect 10 rows):"
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
