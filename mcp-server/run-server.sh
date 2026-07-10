#!/bin/bash
# Garmin MCP Server runner script (local stdio debugging)
# NOTE: InfluxDB is not exposed to the host by default. To use this script,
# temporarily add a ports mapping in compose.yml or use docker exec instead.

cd "$(dirname "$0")"

# Set default environment variables (can be overridden)
export GARMIN_MCP_INFLUXDB_HOST="${GARMIN_MCP_INFLUXDB_HOST:-localhost}"
export GARMIN_MCP_INFLUXDB_PORT="${GARMIN_MCP_INFLUXDB_PORT:-8086}"
export GARMIN_MCP_INFLUXDB_DATABASE="${GARMIN_MCP_INFLUXDB_DATABASE:-GarminStats}"
export GARMIN_MCP_INFLUXDB_USERNAME="${GARMIN_MCP_INFLUXDB_USERNAME:-influxdb_user}"
export GARMIN_MCP_INFLUXDB_PASSWORD="${GARMIN_MCP_INFLUXDB_PASSWORD:-influxdb_secret_password}"
export GARMIN_MCP_TIMEZONE="${GARMIN_MCP_TIMEZONE:-Europe/Berlin}"

# Transport: "stdio" (default, for SSH) or "streamable-http" (for remote/tunnel access)
export GARMIN_MCP_TRANSPORT="${GARMIN_MCP_TRANSPORT:-stdio}"
# HTTP port (only used when transport is streamable-http)
export GARMIN_MCP_HTTP_PORT="${GARMIN_MCP_HTTP_PORT:-8090}"
# Keycloak OAuth (only used for streamable-http transport)
export KEYCLOAK_ISSUER_URL="${KEYCLOAK_ISSUER_URL:-https://auth.batserver.dev/realms/batserver}"
export KEYCLOAK_INTERNAL_URL="${KEYCLOAK_INTERNAL_URL:-http://192.168.178.61:8180/realms/batserver}"
export MCP_RESOURCE_URL="${MCP_RESOURCE_URL:-https://garmin-mcp.batserver.dev}"

# Run the server
exec ~/.local/bin/uv run python -m garmin_mcp.server
