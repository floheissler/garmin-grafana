#!/usr/bin/env bash
# Export the live Grafana dashboard JSON back into the repo file.
# Grafana provisioning is one-way (file -> Grafana), so UI edits live in
# Grafana's internal DB until you run this. After exporting, review with
# `git diff` and commit if you're happy.
#
# Required env:
#   GRAFANA_PASSWORD   admin password
# Optional env (with defaults):
#   GRAFANA_USER             admin
#   GRAFANA_URL              http://localhost:3001
#   GRAFANA_DASHBOARD_UID    feiibsx498gsgb
#   GRAFANA_DASHBOARD_FILE   ./Grafana_Dashboard/Garmin-Grafana-Dashboard.json

set -euo pipefail

if [[ -z "${GRAFANA_PASSWORD:-}" ]]; then
  echo "error: GRAFANA_PASSWORD env var is required" >&2
  echo "usage: GRAFANA_PASSWORD='...' ./export-dashboard.sh" >&2
  exit 1
fi

GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_DASHBOARD_UID="${GRAFANA_DASHBOARD_UID:-feiibsx498gsgb}"
GRAFANA_DASHBOARD_FILE="${GRAFANA_DASHBOARD_FILE:-./Grafana_Dashboard/Garmin-Grafana-Dashboard.json}"

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

http_code=$(curl -sS -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
  -o "$tmpfile" -w "%{http_code}" \
  "${GRAFANA_URL}/api/dashboards/uid/${GRAFANA_DASHBOARD_UID}")

if [[ "$http_code" != "200" ]]; then
  echo "error: Grafana API returned HTTP ${http_code}" >&2
  cat "$tmpfile" >&2
  exit 1
fi

# Unwrap the API envelope (it returns {"dashboard": {...}, "meta": {...}}),
# match the provisioning format (unwrapped dashboard JSON).
python3 - "$tmpfile" "$GRAFANA_DASHBOARD_FILE" <<'PY'
import json, sys
api_resp = json.load(open(sys.argv[1]))
dashboard = api_resp["dashboard"]
with open(sys.argv[2], "w") as f:
    json.dump(dashboard, f, indent=2, sort_keys=False)
    f.write("\n")
print(f"wrote {sys.argv[2]}  (version={dashboard.get('version')}, panels={len(dashboard.get('panels', []))})")
PY

echo
echo "Run 'git diff -- ${GRAFANA_DASHBOARD_FILE}' to review, then commit if you're happy."
