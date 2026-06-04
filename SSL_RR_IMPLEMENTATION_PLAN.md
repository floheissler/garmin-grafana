# Implementation Plan: Step Speed Loss + Respiration Rate for Activities

**Status:** Approved, deferred to implementation week of 2026-06-01.
**Author of investigation:** Claude session 2026-05-28 (`garmin-metrics-mapping-review`).
**Approach chosen:** Option 3 — FIT-native via empirically-identified `unknown_NNN` field IDs.

---

## 1. Context

We bought a Garmin HRM 600 chest strap in March/April 2026. The strap exposes three
new running-dynamics metrics that the watch records but our InfluxDB pipeline
currently ignores:

- **Step Speed Loss (SSL)** — how much you decelerate when your foot hits the ground (cm/s). Lower is better. Launched May 2025.
- **Step Speed Loss Percent (SSL%)** — same thing normalised against forward speed (%).
- **Respiration Rate (RR)** — breaths per minute, including per-second/lap/activity aggregates.

We want this data in InfluxDB so the **Garmin MCP server** (`mcp-server/`) can surface
it to Claude via the existing `get_activity_details` tool (which runs `SELECT *` over
`ActivitySummary` and `ActivityLap`, so new fields are auto-exposed with zero MCP code changes).

### Why Option 3 (not JSON merge, not "wait for fitparse")

- **The data is already in the FIT file** — Garmin writes it under unlabeled field IDs
  (`unknown_134`–`unknown_165`). They haven't published the field-ID → name mapping in
  the public FIT SDK Profile yet, so `fitparse` shows them as `unknown_NNN`.
- The upstream author of this project already uses this exact pattern: `unknown_140` is
  empirically mapped to `GradeAdjustedSpeed` in `src/garmin_grafana/garmin_fetch.py:741`.
  We're extending that pattern, not inventing a new one.
- Avoids any new Garmin API calls (no rate-limit pressure, no extra latency).
- Lives in the same FIT-parsing loop as everything else — clean architecture.
- When `fitparse` eventually updates its profile, we just rename the keys from
  `unknown_NNN` to `step_speed_loss` etc. and the data stays consistent.

---

## 2. Discovered Field Mapping (verified 2026-05-28)

Identified by averaging FIT `unknown_NNN` values across activity `23039184985` and
matching against ground-truth values from the Garmin Connect JSON API.

### Per-second (FIT `record` messages) → `ActivityGPS` measurement

| FIT field | Maps to | Scale | Unit | Verified mean |
|---|---|---|---|---|
| `unknown_108` | Respiration Rate | ÷100 | bpm | 32.15 bpm ✓ |
| `unknown_146` | Step Speed Loss | ÷100 | cm/s | 17.42 cm/s ✓ |
| `unknown_147` | Step Speed Loss Percent | ÷100 | % | 4.96 % ✓ |
| `unknown_140` | (existing) Grade-Adjusted Speed | ÷1000 | m/s | — already in code |

### Per-lap (FIT `lap` messages) → `ActivityLap` measurement

Match verified by **100% per-lap vector agreement across all 10 laps** of the test activity.

| FIT field | Maps to | Scale | Unit | Sample (lap 1) |
|---|---|---|---|---|
| `unknown_136` | Avg Respiration Rate | ÷100 | bpm | 23.73 |
| `unknown_137` | Max Respiration Rate | ÷100 | bpm | 31.14 |
| `unknown_161` | Avg Grade-Adjusted Speed | ÷1000 | m/s | 3.145 *(bonus — not currently in code at lap level)* |
| `unknown_164` | Avg Step Speed Loss | ÷100 | cm/s | 17.82 |
| `unknown_165` | Avg Step Speed Loss Percent | ÷100 | % | 5.49 |

### Activity summary → `ActivitySummary` measurement

`get_activities_by_date` (already called in `get_activity_summary()`) returns these
top-level — **no extra API call needed**. Just extract:

| JSON key | Unit |
|---|---|
| `avgStepSpeedLoss` | cm/s |
| `avgStepSpeedLossPercent` | % |
| `minRespirationRate` | bpm |
| `maxRespirationRate` | bpm |
| `avgRespirationRate` | bpm |

---

## 3. Code Changes

All edits in **`src/garmin_grafana/garmin_fetch.py`**.

### 3.1 `ActivitySummary` — lines ~660-666 (`get_activity_summary()`)

Add to the existing `"fields": { ... }` dict:

```python
'avgStepSpeedLoss': activity.get('avgStepSpeedLoss'),               # cm/s
'avgStepSpeedLossPercent': activity.get('avgStepSpeedLossPercent'), # %
'minRespirationRate': activity.get('minRespirationRate'),           # bpm
'maxRespirationRate': activity.get('maxRespirationRate'),           # bpm
'avgRespirationRate': activity.get('avgRespirationRate'),           # bpm
```

### 3.2 `ActivityGPS` — lines ~731-754 (per-record loop in `fetch_activity_GPS()`)

Add to the existing `"fields": { ... }` dict, mirroring the `unknown_140` pattern:

```python
"RespirationRate": (parsed_record.get("unknown_108") / 100.0) if parsed_record.get("unknown_108") else None,        # bpm
"StepSpeedLoss": (parsed_record.get("unknown_146") / 100.0) if parsed_record.get("unknown_146") else None,          # cm/s
"StepSpeedLossPercent": (parsed_record.get("unknown_147") / 100.0) if parsed_record.get("unknown_147") else None,   # %
```

### 3.3 `ActivityLap` — lines ~820-847 (per-lap loop in `fetch_activity_GPS()`)

Add to the existing `"fields": { ... }` dict:

```python
"Avg_RespirationRate": (lap_record.get("unknown_136") / 100.0) if lap_record.get("unknown_136") else None,           # bpm
"Max_RespirationRate": (lap_record.get("unknown_137") / 100.0) if lap_record.get("unknown_137") else None,           # bpm
"Avg_GradeAdjustedSpeed": (lap_record.get("unknown_161") / 1000.0) if lap_record.get("unknown_161") else None,       # m/s
"Avg_StepSpeedLoss": (lap_record.get("unknown_164") / 100.0) if lap_record.get("unknown_164") else None,             # cm/s
"Avg_StepSpeedLossPercent": (lap_record.get("unknown_165") / 100.0) if lap_record.get("unknown_165") else None,      # %
```

### 3.4 Suggested code comment

Add a single comment block above the new lines, e.g.:

```python
# Empirically-identified HRM 600 fields (mapping discovered 2026-05-28, see SSL_RR_IMPLEMENTATION_PLAN.md).
# These mirror the unknown_140 pattern already used for GradeAdjustedSpeed above.
# When fitparse releases an updated FIT Profile, rename these to step_speed_loss / respiration_rate / etc.
```

---

## 4. Deploy + Verify

### 4.1 Rebuild

```bash
cd ~/docker/garmin-grafana
docker compose up -d --build
docker logs garmin-fetch-data --tail 30   # confirm no startup errors
```

### 4.2 Force-process one recent run

```bash
docker compose run --rm \
  -e FORCE_REPROCESS_ACTIVITIES=True \
  -e MANUAL_START_DATE=2026-05-28 \
  -e MANUAL_END_DATE=2026-05-28 \
  garmin-fetch-data
```

### 4.3 Verify with InfluxDB queries

```bash
# ActivitySummary should have the 5 new fields populated
docker exec influxdb influx -database GarminStats -execute \
  "SELECT avgStepSpeedLoss, avgStepSpeedLossPercent, avgRespirationRate FROM ActivitySummary WHERE Activity_ID = 23039184985"

# ActivityLap should have the 5 new fields populated (10 laps)
docker exec influxdb influx -database GarminStats -execute \
  "SELECT Avg_StepSpeedLoss, Avg_StepSpeedLossPercent, Avg_RespirationRate, Max_RespirationRate, Avg_GradeAdjustedSpeed FROM ActivityLap WHERE Activity_ID = 23039184985"

# ActivityGPS should have new per-second fields populated
docker exec influxdb influx -database GarminStats -execute \
  "SELECT mean(StepSpeedLoss), mean(StepSpeedLossPercent), mean(RespirationRate) FROM ActivityGPS WHERE Activity_ID = 23039184985"
```

**Expected values for activity 23039184985 (May 28 morning run):**
- `avgStepSpeedLoss` ≈ 17.42 cm/s
- `avgStepSpeedLossPercent` ≈ 4.96 %
- `avgRespirationRate` ≈ 32.15 bpm
- Lap 1 `Avg_StepSpeedLoss` ≈ 17.82 cm/s, `Avg_RespirationRate` ≈ 23.73 bpm

If the means come back close to those, the mapping is confirmed and the fix is live.

### 4.4 Confirm MCP exposure

From Claude Desktop, ask: *"Tell me about my May 28 morning run."* — the SSL and respiration values should appear in the MCP tool's output without any MCP code change (because `get_activity_details` does `SELECT *` over `ActivitySummary` and `ActivityLap`).

---

## 5. Backfill

After verification succeeds for the test activity, reprocess historical runs since
the strap was purchased:

```bash
docker compose run --rm \
  -e FORCE_REPROCESS_ACTIVITIES=True \
  -e MANUAL_START_DATE=2026-03-01 \
  -e MANUAL_END_DATE=2026-05-28 \
  garmin-fetch-data
```

This re-reads each activity's FIT file and re-writes the InfluxDB points
(InfluxDB upserts on identical timestamp+tags, so this is idempotent).

**Cost estimate:** ~30 running activities × ~1 API call each (download_activity) × 5 s
rate limit ≈ 2.5 minutes. Well within Garmin's tolerance.

**Pre-flight (recommended):** take an LVM snapshot first so we have an undo button:

```bash
~/lvm-snapshot.sh create
# ... run backfill, verify ...
~/lvm-snapshot.sh remove   # all good
```

---

## 6. Cleanup

Temporary investigation script (`inspect_fit.py`) was already removed at the end of
the planning session on 2026-05-28 — nothing to clean up there.

After implementation succeeds, commit + push to the fork:

```bash
cd ~/docker/garmin-grafana
git add src/garmin_grafana/garmin_fetch.py SSL_RR_IMPLEMENTATION_PLAN.md
git commit -m "Add HRM 600 metrics: Step Speed Loss, SSL%, Respiration Rate"
git push origin main
```

Without the push, the next `docker compose up -d --build` from a fresh clone (or after
merging upstream) would rebuild without the new code.

---

## 7. Risks & Rollback

| Risk | Mitigation |
|---|---|
| FIT field IDs change in a future Garmin firmware update | The plan documents which `unknown_NNN` maps to what; re-run `inspect_fit.py` (or its equivalent) to re-verify if values look wrong |
| Code bug crashes the fetcher loop | `git checkout src/garmin_grafana/garmin_fetch.py` reverts; `docker compose up -d --build` restores |
| Backfill writes wrong values to existing DB rows | LVM snapshot before backfill = clean restore point |
| Upstream merge conflict on `garmin_fetch.py` | Likely minor — we're only adding lines inside existing dict literals. Re-apply on merge. |
| Fitparse updates its profile (renames `unknown_NNN` to real names) | Our `unknown_NNN` keys would stop matching; refactor to `step_speed_loss` etc. when that ships |

DB risk is **essentially zero** — InfluxDB 1.x is schemaless for fields, so adding new
fields to existing measurements is a no-op for existing rows.

---

## 8. Open / Future Ideas

- **Mystery unknowns** — `unknown_134`, `_135`, `_143`, `_87`, `_124` etc. likely
  contain: Impact Load Factor, Performance Condition, Stamina, Body Battery during run.
  A follow-up could identify them by per-second vector matching against
  `activityDetailMetrics` from `get_activity_details`. Not blocking SSL/RR work.
- **Upstream contribution** — once verified, consider opening a PR against
  `arpanghosh8453/garmin-grafana` so the community benefits.
- **Grafana dashboard panels** — once data is flowing, add SSL/SSL%/RR panels to the
  running-dynamics row of the dashboard.

---

## 9. Quick reference (paste-ready commands)

```bash
# 1. Edit the file (sections 3.1–3.4 above)
$EDITOR ~/docker/garmin-grafana/src/garmin_grafana/garmin_fetch.py

# 2. Rebuild
cd ~/docker/garmin-grafana && docker compose up -d --build

# 3. Test on May 28 run
docker compose run --rm -e FORCE_REPROCESS_ACTIVITIES=True \
  -e MANUAL_START_DATE=2026-05-28 -e MANUAL_END_DATE=2026-05-28 \
  garmin-fetch-data

# 4. Verify (expect ~17.42 cm/s, 4.96%, 32.15 bpm)
docker exec influxdb influx -database GarminStats -execute \
  "SELECT avgStepSpeedLoss, avgStepSpeedLossPercent, avgRespirationRate FROM ActivitySummary WHERE Activity_ID = 23039184985"

# 5. LVM snapshot + backfill
~/lvm-snapshot.sh create
docker compose run --rm -e FORCE_REPROCESS_ACTIVITIES=True \
  -e MANUAL_START_DATE=2026-03-01 -e MANUAL_END_DATE=2026-05-28 \
  garmin-fetch-data
~/lvm-snapshot.sh remove

# 6. Commit (temp file already removed on 2026-05-28)
cd ~/docker/garmin-grafana && git add -p src/ SSL_RR_IMPLEMENTATION_PLAN.md && git commit && git push origin main
```
