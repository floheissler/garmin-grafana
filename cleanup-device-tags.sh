#!/usr/bin/env bash
# Drop phantom Device-tagged series caused by the pre-pin GARMIN_DEVICENAME drift bug.
# Idempotent: DROP SERIES is a no-op on already-removed series, safe to re-run.
# Pre-req: the compose env var pin (GARMIN_DEVICENAME=fenix 8 - 51mm, AMOLED) is live.
set -euo pipefail

WATCH='fenix 8 - 51mm, AMOLED'
BP='Index™ BPM'
STRAP='HRM 600'

# Measurements that should only ever have the watch as Device.
WATCH_OWNED=(
  DailyStats
  SleepSummary SleepIntraday
  HRV_Intraday
  HeartRateIntraday StepsIntraday StressIntraday BodyBatteryIntraday BreathingRateIntraday
  TrainingStatus TrainingReadiness
  VO2_Max FitnessAge RacePredictions
  HillScore EnduranceScore LactateThreshold
  BodyComposition
  ActivitySummary ActivityLap ActivityGPS ActivitySession ActivityLength
)

echo ">>> Dropping non-watch series from watch-owned measurements..."
{
  for m in "${WATCH_OWNED[@]}"; do
    printf 'DROP SERIES FROM "%s" WHERE Device = '"'%s'"';\n' "$m" "$BP"
    printf 'DROP SERIES FROM "%s" WHERE Device = '"'%s'"';\n' "$m" "$STRAP"
  done
} | docker exec -i influxdb influx -database GarminStats

echo ">>> Dropping non-cuff series from BloodPressure..."
# 'DEVICE' is Garmin's API sourceType value (not a real device name) — leftover
# from the first pass of the fix before introducing GARMIN_BPM_DEVICENAME.
{
  printf 'DROP SERIES FROM "BloodPressure" WHERE Device = '"'%s'"';\n' "$WATCH"
  printf 'DROP SERIES FROM "BloodPressure" WHERE Device = '"'%s'"';\n' "$STRAP"
  printf 'DROP SERIES FROM "BloodPressure" WHERE Device = '"'DEVICE'"';\n'
} | docker exec -i influxdb influx -database GarminStats

echo ""
echo ">>> Self-verify: SHOW TAG VALUES per measurement"
for m in "${WATCH_OWNED[@]}" BloodPressure; do
  echo "--- $m ---"
  docker exec influxdb influx -database GarminStats -execute \
    "SHOW TAG VALUES FROM \"$m\" WITH KEY = Device" -format csv | tail -n +2
done

echo ""
echo ">>> Done. Watch-owned measurements should show only '$WATCH'; BloodPressure only '$BP'."
