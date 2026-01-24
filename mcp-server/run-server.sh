#!/bin/bash
# Garmin MCP Server runner script
# Used for connecting via SSH from remote machines

cd "$(dirname "$0")"

# Set default environment variables (can be overridden)
export GARMIN_MCP_INFLUXDB_HOST="${GARMIN_MCP_INFLUXDB_HOST:-localhost}"
export GARMIN_MCP_INFLUXDB_PORT="${GARMIN_MCP_INFLUXDB_PORT:-8086}"
export GARMIN_MCP_INFLUXDB_DATABASE="${GARMIN_MCP_INFLUXDB_DATABASE:-GarminStats}"
export GARMIN_MCP_INFLUXDB_USERNAME="${GARMIN_MCP_INFLUXDB_USERNAME:-influxdb_user}"
export GARMIN_MCP_INFLUXDB_PASSWORD="${GARMIN_MCP_INFLUXDB_PASSWORD:-influxdb_secret_password}"
export GARMIN_MCP_TIMEZONE="${GARMIN_MCP_TIMEZONE:-Europe/Berlin}"

# Run the server
exec ~/.local/bin/uv run python -m garmin_mcp.server
