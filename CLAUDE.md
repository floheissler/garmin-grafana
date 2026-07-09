# Garmin-Grafana Project Guidelines

## Local Installation (Batman's Homeserver)

| Item | Value |
|------|-------|
| **Grafana URL** | http://192.168.178.61:3001 |
| **Login** | `admin` / (changed on first login) |
| **Timezone** | `Europe/Berlin` |
| **Sync Interval** | Every 5 minutes |
| **Data imported** | From 2025-10-01 |

### Quick Commands
```bash
# View sync logs
docker logs garmin-fetch-data --tail 50

# Re-authenticate (when token expires ~1 year)
docker compose run --rm garmin-fetch-data

# Import more historical data
docker compose run --rm -e MANUAL_START_DATE=YYYY-MM-DD -e MANUAL_END_DATE=YYYY-MM-DD garmin-fetch-data

# Update stack (rebuild from local source)
docker compose up -d --build

# Export to CSV
docker exec garmin-fetch-data uv run /app/garmin_grafana/influxdb_exporter.py --last-n-days 30
```

### Multi-Device Setup

This account has three syncing devices (fenix 8 watch, Index™ BPM cuff, HRM 600 strap). User-facing setup guidance lives in the [README's "Additional configuration" section](./README.md#additional-configuration-and-environment-variables) (multi-device ✅ entry).

**Notes for future maintainers:**
- `GARMIN_BPM_DEVICENAME` is a local addition (not in upstream). The code change is `garmin_fetch.py:1172`. If you pull from upstream, make sure both the env var pin in `compose.yml` and that code line survive the merge.
- The `Device` tag pin is what keeps non-DeviceSync measurements stable. If a new device that owns its own measurement gets added (e.g. a smart scale for BodyComposition), extend the pattern: a new `GARMIN_<X>_DEVICENAME` env var + a tag override in the relevant write path. `DeviceSync` is the only measurement that legitimately varies — leave that alone.

### Recovery Time Unit

`TrainingReadiness.recoveryTime` from Garmin's API is in **minutes**, not hours. Stored raw in InfluxDB. MCP labels it `recovery_time_minutes`. Grafana panels should divide by 60 for hours display. (The FIT-file path at `garmin_fetch.py:792` writes `ActivitySession.Recovery_Time` from a different field — FIT spec convention is seconds, possibly disagrees with this; only relevant if you actually query it.)

### InfluxDB Backups

Automated monthly backups via crontab (`0 4 1 * *` — 1st of each month at 4 AM).

- **Script**: `./create-backup.sh`
- **Local backup**: `./influxdb_backups/<YYYY-MM-DD_HH-MM>/`
- **Off-site copy**: `/mnt/usb-backup/garmin-influxdb/` (if USB drive mounted)
- **Retention**: Backups older than 30 days are automatically deleted (both local and USB)
- **Format**: InfluxDB portable backup (`.tar.gz` shards + `.manifest` + `.meta`)
- **USB setup**: Format drive as ext4, add to `/etc/fstab` with `nofail` option using its UUID

```bash
# Manual backup
./backup-influxdb.sh

# Restore from backup
docker exec influxdb influxd restore -portable -db GarminStats /tmp/influxdb_backup
```

### Database Schema
See [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for complete InfluxDB schema documentation including all measurements, fields, and example queries.

### Git Repository
This is a fork of the upstream project with local customizations.

| Remote | Repository | Purpose |
|--------|------------|---------|
| `origin` | [floheissler/garmin-grafana](https://github.com/floheissler/garmin-grafana) | Our fork (push here) |
| `upstream` | [arpanghosh8453/garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana) | Original project (pull updates) |

The Docker image is built locally from our fork (not pulled from a registry), so after merging upstream changes or making local edits, rebuild with `docker compose up -d --build`.

```bash
# Push changes to our fork
git push origin main

# Pull upstream updates, rebuild
git fetch upstream && git merge upstream/main && git push origin main
docker compose up -d --build
```

---

## MCP Server (Claude Integration)

Query Garmin health data directly from Claude using the MCP (Model Context Protocol) server.

**Location**: `mcp-server/`

### Available Tools (13)

| Tool | Description |
|------|-------------|
| `get_daily_summary` | Daily metrics (steps, HR, stress, body battery) |
| `get_sleep` | Sleep score, stages, HRV, breathing rate |
| `get_heart_rate` | HR data with smart aggregation |
| `get_stress_body_battery` | Stress levels and body battery |
| `get_activities` | List workouts with distance, pace, HR |
| `get_activity_details` | Full activity data: laps, pace, cadence, power, HR zones, training effect, running dynamics |
| `get_hrv` | Heart rate variability trends (key recovery metric) |
| `get_trends` | Long-term trend analysis (steps, HR, weight, etc.) |
| `get_fitness_metrics` | VO2 max, fitness age, race predictions |
| `get_body_composition` | Weight tracking |
| `get_blood_pressure` | Blood pressure readings (systolic, diastolic, pulse) |
| `get_training_status` | Training status, readiness, load, and recovery |
| `query_measurement` | Advanced: direct InfluxQL queries |

### Smart Aggregation

Data is automatically aggregated based on query duration to prevent context overflow:

| Duration | Aggregation |
|----------|-------------|
| 1 day | Raw data |
| 2-7 days | Hourly averages |
| 8-30 days | Daily values |
| 31-90 days | Daily with trends |
| 91+ days | Weekly/monthly |

Override with `aggregation="raw"` for full data (max 5000 points).

### Running Locally (stdio, for SSH)

```bash
cd mcp-server
./run-server.sh
```

### Running as HTTP Server (for remote access via Cloudflare Tunnel)

```bash
cd mcp-server
GARMIN_MCP_TRANSPORT=streamable-http ./run-server.sh
```

This starts the MCP server on port 8090 with OAuth 2.1 authentication via Keycloak.

### Authentication

**Remote (streamable-http)**: OAuth 2.1 via Keycloak. The MCP SDK handles everything automatically:
- Serves `/.well-known/oauth-protected-resource` pointing to Keycloak as the authorization server
- Returns 401 with `WWW-Authenticate` header for unauthenticated requests
- Validates Keycloak-issued JWTs using the JWKS endpoint (fetched internally, not through Cloudflare)
- `KeycloakTokenVerifier` in `server.py` implements the SDK's `TokenVerifier` protocol

**Local (stdio)**: No authentication — used for SSH-piped connections from Claude Desktop/Code.

### Client Configuration

Register in Claude.ai or ChatGPT as a remote MCP server — syncs across all devices automatically:
- **URL**: `https://garmin-mcp.batserver.dev/mcp`
- **Auth**: OAuth — auto-discovered via protected resource metadata
- **Login**: Keycloak (`auth.batserver.dev`, realm `batserver`)

The stdio transport is still available as a fallback for local debugging:
```bash
cd mcp-server && ./run-server.sh  # defaults to stdio
```

### Example Queries

- "What was my sleep score last night?" → `get_sleep(date="2026-01-24")`
- "Show my step trend over 3 months" → `get_trends(metric="steps", duration="90d")`
- "List my runs this month" → `get_activities(activity_type="running", duration="30d")`
- "Tell me about yesterday's run" → `get_activity_details(activity_id=12345)`
- "How's my HRV trending?" → `get_hrv(duration="30d")`
- "What's my current VO2 max?" → `get_fitness_metrics()`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GARMIN_MCP_INFLUXDB_HOST` | `localhost` | InfluxDB host |
| `GARMIN_MCP_INFLUXDB_PORT` | `8086` | InfluxDB port |
| `GARMIN_MCP_INFLUXDB_DATABASE` | `GarminStats` | Database name |
| `GARMIN_MCP_INFLUXDB_USERNAME` | `influxdb_user` | DB username |
| `GARMIN_MCP_INFLUXDB_PASSWORD` | `influxdb_secret_password` | DB password |
| `GARMIN_MCP_TIMEZONE` | `Europe/Berlin` | Timezone for queries |
| `GARMIN_MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `streamable-http` |
| `GARMIN_MCP_HTTP_PORT` | `8090` | HTTP port (streamable-http only) |
| `KEYCLOAK_ISSUER_URL` | `https://auth.batserver.dev/realms/batserver` | Keycloak realm URL (public, for token issuer validation) |
| `KEYCLOAK_INTERNAL_URL` | `http://192.168.178.61:8180/realms/batserver` | Keycloak realm URL (internal, for JWKS fetching — bypasses Cloudflare) |
| `MCP_RESOURCE_URL` | `https://garmin-mcp.batserver.dev` | Public URL of this MCP server (used in OAuth resource metadata) |

---

## Project Overview

**Garmin-Grafana** is a Docker-based system that fetches health/fitness data from Garmin Connect and stores it in InfluxDB for visualization with Grafana dashboards. It enables self-hosted ownership of personal health metrics.

**Author**: Arpan Ghosh | **Repository**: https://github.com/arpanghosh8453/garmin-grafana | **Version**: 0.3.0

### Core Value Proposition
- Local ownership of sensitive health data
- Custom analytics beyond Garmin's app
- Historical data preservation
- Multi-device and multi-user support

## Architecture

```
Garmin Connect Cloud
        │
        │ OAuth 2.0 + REST API
        ▼
┌─────────────────────────────┐
│  garmin-fetch-data          │  Python 3.13 + uv
│  (garmin_fetch.py)          │  Fetches, transforms, stores
└─────────────┬───────────────┘
              │ InfluxQL Protocol
              ▼
┌─────────────────────────────┐
│  InfluxDB 1.11              │  Time-series database
│  Database: GarminStats      │  25+ measurements
└─────────────┬───────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌───────────┐    ┌──────────────────┐
│  Grafana  │    │   MCP Server     │
│  :3001    │    │  :8090 (HTTP)    │
└───────────┘    └───────┬──────────┘
                         │
                  Cloudflare Tunnel
              (garmin-mcp.batserver.dev)
                         │
                         ▼
              ┌──────────────────┐
              │ Claude.ai /      │  All devices:
              │ ChatGPT          │  web, mobile,
              │                  │  desktop, Code
              └────────┬─────────┘
                       │ OAuth 2.1
                       ▼
              ┌──────────────────┐
              │    Keycloak      │
              │ auth.batserver   │
              │     .dev         │
              └──────────────────┘
```

## Key Files

| Path | Purpose |
|------|---------|
| `src/garmin_grafana/garmin_fetch.py` | Main application (~1400 lines) - API client, data transformation, InfluxDB writes |
| `src/garmin_grafana/influxdb_exporter.py` | CSV export utility for external analysis |
| `compose-example.yml` | Docker Compose stack definition (3 containers) |
| `Dockerfile` | Multi-arch container build (amd64, arm64) |
| `Grafana_Dashboard/Garmin-Grafana-Dashboard.json` | Pre-configured dashboard |
| `Grafana_Datasource/influxdb.yaml` | Auto-provisioned datasource |
| `easy-install.sh` | One-command setup script |
| `k8s/` | Kubernetes Helm chart |
| `pyproject.toml` | Python dependencies via uv |
| `mcp-server/` | MCP server for Claude integration |

## Technology Stack

- **Runtime**: Python 3.13, uv package manager
- **Core Libraries**: garminconnect, garth (auth), fitparse (FIT files), pandas, influxdb
- **Databases**: InfluxDB 1.11 (recommended), InfluxDB 3.x (supported)
- **Visualization**: Grafana with hourly-heatmap-plugin
- **Deployment**: Docker, Docker Compose, Kubernetes/Helm
- **CI/CD**: GitHub Actions (multi-arch builds)

## Development Guidelines

### Code Style
- Single-file architecture for main logic (`garmin_fetch.py`)
- Environment variables for all configuration (no hardcoded values)
- Comprehensive error handling with graceful degradation
- Rate limiting between API calls (default 5 seconds)
- Batched writes (20,000 points max per write)

### Data Flow Pattern
1. **Auth**: Load cached OAuth tokens → re-auth if expired
2. **Fetch**: Poll Garmin API for new data since last sync
3. **Transform**: Convert JSON/FIT files → InfluxDB points
4. **Store**: Batch write to InfluxDB with idempotent timestamps

### Error Handling Conventions
- HTTP 429 (rate limit): Configurable backoff
- HTTP 500: Skip date after `MAX_CONSECUTIVE_500_ERRORS`
- Connection errors: Retry with `FETCH_FAILED_WAIT_SECONDS` delay
- Token expiration: Prompt for re-authentication

### Key Design Decisions
- **InfluxDB 1.x over 2.x**: Better compatibility, simpler setup
- **Reverse chronological fetch**: Recent data prioritized
- **FIT over TCX**: Binary format has richer data
- **Non-root container user**: Security best practice

## Common Tasks

### Running Locally (Development)
```bash
# Install dependencies
uv sync

# Run directly (requires local InfluxDB)
uv run src/garmin_grafana/garmin_fetch.py
```

### Docker Commands
```bash
# Start full stack
docker compose up -d

# View logs
docker compose logs -f garmin-fetch-data

# Re-authenticate (token expired)
docker compose run --rm garmin-fetch-data

# Export data to CSV
docker exec garmin-fetch-data uv run /app/garmin_grafana/influxdb_exporter.py --last-n-days 30

# Bulk update historical data
MANUAL_START_DATE=2024-01-01 MANUAL_END_DATE=2024-06-30 docker compose up garmin-fetch-data
```

### Building Docker Image
```bash
docker build -t garmin-fetch-data:local .
```

## Configuration Reference

### Required Variables
| Variable | Description |
|----------|-------------|
| `INFLUXDB_HOST` | InfluxDB hostname (default: `influxdb`) |
| `INFLUXDB_PORT` | InfluxDB port (default: `8086`) |
| `INFLUXDB_USERNAME` | Database user |
| `INFLUXDB_PASSWORD` | Database password |
| `INFLUXDB_DATABASE` | Database name (default: `GarminStats`) |

### Optional Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `FETCH_SELECTION` | (all) | Comma-separated metrics to fetch |
| `UPDATE_INTERVAL_SECONDS` | `300` | Polling interval |
| `RATE_LIMIT_CALLS_SECONDS` | `5` | Delay between API calls |
| `KEEP_FIT_FILES` | `false` | Store downloaded FIT files |
| `USER_TIMEZONE` | (auto) | Override timezone detection |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Fetch Selection Options
`daily_stats`, `sleep`, `hrv`, `steps_intraday`, `hr_intraday`, `stress_intraday`, `body_battery_intraday`, `breathing_rate_intraday`, `spo2_intraday`, `activities`, `body_composition`, `training_status`, `training_readiness`, `race_predictions`, `vo2_max`, `fitness_age`, `hill_score`, `endurance_score`, `blood_pressure`

## Database Schema

### Key Measurements
- `DailyStats` - Daily aggregates (steps, calories, stress)
- `SleepSummary` / `SleepIntraday` - Sleep metrics
- `HeartRateIntraday` / `StepsIntraday` / `StressIntraday` - Per-minute data
- `ActivitySummary` / `ActivityGPS` - Workout data with GPS traces
- `BodyComposition` - Weight, body fat, muscle mass
- `TrainingStatus` / `TrainingReadiness` - Training load metrics

### Tag Structure
- `Device` - Watch model
- `ActivityID` - Unique activity identifier
- `ActivitySelector` - Grafana variable key (Name + ID)

## Testing & Debugging

### Log Analysis
```bash
# Check for auth issues
docker compose logs garmin-fetch-data | grep -i "token\|auth\|login"

# Check for API errors
docker compose logs garmin-fetch-data | grep -i "error\|failed\|429\|500"
```

### Common Issues
1. **Rate limited (429)**: Wait 24h or change IP/network
2. **Token expired**: Run container interactively to re-auth
3. **Missing intraday data >6 months**: Garmin "cold storage" - open Garmin app to refresh
4. **Timezone issues**: Set `USER_TIMEZONE` explicitly

### InfluxDB Queries (via Grafana or CLI)
```sql
-- Recent heart rate data
SELECT * FROM HeartRateIntraday WHERE time > now() - 1h

-- Activity summary
SELECT * FROM ActivitySummary ORDER BY time DESC LIMIT 10

-- Check last sync time
SELECT * FROM DeviceSync ORDER BY time DESC LIMIT 1
```

## CI/CD Pipeline

### GitHub Actions
- **prod.push.yml**: Builds multi-arch images on push to `main`
  - Pushes to Docker Hub: `thisisarpanghosh/garmin-fetch-data:latest`
  - Pushes to GHCR: `ghcr.io/arpanghosh8453/garmin-fetch-data:latest`

### Release Process
- Version managed in `pyproject.toml`
- Semantic versioning (currently 0.3.0)

## Contributing

### Before Submitting PRs
1. Test with both InfluxDB 1.x and 3.x if touching database code
2. Ensure multi-arch compatibility (avoid x86-specific code)
3. Update README.md for user-facing changes
4. Follow existing code patterns in `garmin_fetch.py`

### Adding New Metrics
1. Add fetch function in `garmin_fetch.py`
2. Add transformation to InfluxDB points
3. Add to `FETCH_SELECTION` options
4. Document in README.md
5. (Optional) Add Grafana dashboard panel

## Limitations & Constraints

- Requires data synced to Garmin Cloud first (no direct watch sync)
- OAuth tokens expire ~1 year (MFA users must re-auth)
- Garmin rate limits logins aggressively
- InfluxDB 2.x not officially supported
- InfluxDB 3.x OSS has 72-hour query limit
