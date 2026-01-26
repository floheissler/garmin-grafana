# Garmin InfluxDB Database Schema

This document describes the InfluxDB measurements stored in the `GarminStats` database.

## Overview

| Category | Measurements | Granularity |
|----------|--------------|-------------|
| **Daily Summaries** | DailyStats, SleepSummary, FitnessAge, RacePredictions, VO2_Max | Per day |
| **Intraday Metrics** | HeartRateIntraday, StepsIntraday, StressIntraday, BodyBatteryIntraday, BreathingRateIntraday | Per minute |
| **Sleep Details** | SleepIntraday, HRV_Intraday | Per minute (overnight) |
| **Activities** | ActivitySummary, ActivityGPS, ActivityLap, ActivitySession | Per activity/lap/point |
| **Body** | BodyComposition | Per weigh-in |
| **System** | DeviceSync, DemoPoint | Metadata |

---

## Daily Summaries

### DailyStats
Daily aggregate health metrics.

| Field | Type | Description |
|-------|------|-------------|
| `totalSteps` | integer | Total steps for the day |
| `totalDistanceMeters` | integer | Total distance walked/run |
| `activeKilocalories` | float | Calories burned from activity |
| `bmrKilocalories` | float | Basal metabolic rate calories |
| `restingHeartRate` | integer | Resting heart rate (bpm) |
| `minHeartRate` | integer | Minimum heart rate |
| `maxHeartRate` | integer | Maximum heart rate |
| `minAvgHeartRate` | integer | Minimum average heart rate |
| `maxAvgHeartRate` | integer | Maximum average heart rate |
| `floorsAscended` | float | Floors climbed |
| `floorsDescended` | float | Floors descended |
| `floorsAscendedInMeters` | float | Elevation gain (meters) |
| `floorsDescendedInMeters` | float | Elevation loss (meters) |
| `moderateIntensityMinutes` | integer | Moderate activity minutes |
| `vigorousIntensityMinutes` | integer | Vigorous activity minutes |
| `sedentarySeconds` | integer | Time spent sedentary |
| `activeSeconds` | integer | Time spent active |
| `highlyActiveSeconds` | integer | Time spent highly active |
| `sleepingSeconds` | integer | Time spent sleeping |
| `stressPercentage` | float | Overall stress percentage |
| `restStressPercentage` | float | Rest stress percentage |
| `lowStressPercentage` | float | Low stress percentage |
| `mediumStressPercentage` | float | Medium stress percentage |
| `highStressPercentage` | float | High stress percentage |
| `activityStressPercentage` | float | Activity stress percentage |
| `uncategorizedStressPercentage` | float | Uncategorized stress percentage |
| `stressDuration` | integer | Total stress duration (seconds) |
| `restStressDuration` | integer | Rest stress duration |
| `lowStressDuration` | integer | Low stress duration |
| `mediumStressDuration` | integer | Medium stress duration |
| `highStressDuration` | integer | High stress duration |
| `activityStressDuration` | integer | Activity stress duration |
| `totalStressDuration` | integer | Total stress duration |
| `uncategorizedStressDuration` | integer | Uncategorized stress duration |
| `bodyBatteryHighestValue` | integer | Highest body battery (0-100) |
| `bodyBatteryLowestValue` | integer | Lowest body battery |
| `bodyBatteryAtWakeTime` | integer | Body battery at wake |
| `bodyBatteryChargedValue` | integer | Body battery charged |
| `bodyBatteryDrainedValue` | integer | Body battery drained |
| `bodyBatteryDuringSleep` | integer | Body battery change during sleep |
| `averageSpo2` | float | Average blood oxygen % |
| `lowestSpo2` | integer | Lowest blood oxygen % |

### SleepSummary
Nightly sleep summary metrics.

| Field | Type | Description |
|-------|------|-------------|
| `sleepScore` | integer | Overall sleep score (0-100) |
| `sleepTimeSeconds` | integer | Total sleep duration |
| `deepSleepSeconds` | integer | Deep sleep duration |
| `lightSleepSeconds` | integer | Light sleep duration |
| `remSleepSeconds` | integer | REM sleep duration |
| `awakeSleepSeconds` | integer | Time awake during sleep |
| `awakeCount` | integer | Number of times woken |
| `restlessMomentsCount` | integer | Restless moments count |
| `avgOvernightHrv` | float | Average overnight HRV |
| `avgSleepStress` | float | Average sleep stress |
| `restingHeartRate` | integer | Resting heart rate |
| `averageRespirationValue` | float | Average breathing rate |
| `highestRespirationValue` | float | Highest breathing rate |
| `lowestRespirationValue` | float | Lowest breathing rate |
| `averageSpO2Value` | float | Average blood oxygen |
| `highestSpO2Value` | integer | Highest blood oxygen |
| `lowestSpO2Value` | integer | Lowest blood oxygen |
| `bodyBatteryChange` | integer | Body battery change overnight |

### FitnessAge
Garmin's fitness age calculation.

| Field | Type | Description |
|-------|------|-------------|
| `fitnessAge` | float | Calculated fitness age |
| `chronologicalAge` | float | Actual age |
| `achievableFitnessAge` | float | Best achievable fitness age |

### RacePredictions
Predicted race times based on fitness.

| Field | Type | Description |
|-------|------|-------------|
| `time5K` | integer | Predicted 5K time (seconds) |
| `time10K` | integer | Predicted 10K time (seconds) |
| `timeHalfMarathon` | integer | Predicted half marathon time |
| `timeMarathon` | integer | Predicted marathon time |

### VO2_Max
VO2 max estimates.

| Field | Type | Description |
|-------|------|-------------|
| `VO2_max_value` | float | VO2 max (ml/kg/min) |

---

## Intraday Metrics

### HeartRateIntraday
Per-minute heart rate readings (24/7).

| Field | Type | Description |
|-------|------|-------------|
| `HeartRate` | integer | Heart rate (bpm) |

**Granularity:** ~1-2 minutes, ~720 readings/day

### StepsIntraday
Per-interval step counts.

| Field | Type | Description |
|-------|------|-------------|
| `StepsCount` | integer | Steps in interval |

**Granularity:** ~15 minutes, ~96 readings/day

### StressIntraday
Per-minute stress and body battery levels.

| Field | Type | Description |
|-------|------|-------------|
| `stressLevel` | integer | Stress level (0-100, -1 = activity) |
| `bodyBattery` | integer | Body battery level (0-100) |

**Granularity:** ~3 minutes, ~480 readings/day

### BodyBatteryIntraday
Per-minute body battery readings.

| Field | Type | Description |
|-------|------|-------------|
| `BodyBatteryLevel` | integer | Body battery (0-100) |

### BreathingRateIntraday
Per-minute breathing rate.

| Field | Type | Description |
|-------|------|-------------|
| `BreathingRate` | float | Breaths per minute |

---

## Sleep Details

### SleepIntraday
Per-minute sleep stage and vitals during sleep.

| Field | Type | Description |
|-------|------|-------------|
| `SleepStageLevel` | float | Sleep stage (deep/light/REM/awake) |
| `SleepStageSeconds` | integer | Duration in stage |
| `SleepMovementActivityLevel` | float | Movement intensity |
| `SleepMovementActivitySeconds` | integer | Movement duration |
| `heartRate` | integer | Heart rate during sleep |
| `hrvData` | float | HRV value |
| `respirationValue` | float | Breathing rate |
| `spo2Reading` | integer | Blood oxygen % |
| `stressValue` | integer | Stress level |
| `bodyBattery` | integer | Body battery |
| `sleepRestlessValue` | integer | Restlessness score |

### HRV_Intraday
Heart rate variability during sleep.

| Field | Type | Description |
|-------|------|-------------|
| `hrvValue` | integer | HRV value (ms) |

---

## Activities

### ActivitySummary
Summary metrics for each activity/workout.

| Field | Type | Description |
|-------|------|-------------|
| `Activity_ID` | integer | Unique activity ID |
| `Device_ID` | integer | Device ID |
| `activityName` | string | Activity name |
| `activityType` | string | Type (running, cycling, etc.) |
| `distance` | float | Distance (meters) |
| `elapsedDuration` | float | Total duration (seconds) |
| `movingDuration` | float | Moving time (seconds) |
| `calories` | float | Total calories |
| `bmrCalories` | float | BMR calories |
| `averageHR` | float | Average heart rate |
| `maxHR` | float | Maximum heart rate |
| `averageSpeed` | float | Average speed (m/s) |
| `maxSpeed` | float | Maximum speed (m/s) |
| `lapCount` | integer | Number of laps |
| `locationName` | string | Location name |
| `hrTimeInZone_1` | float | Time in HR zone 1 |
| `hrTimeInZone_2` | float | Time in HR zone 2 |
| `hrTimeInZone_3` | float | Time in HR zone 3 |
| `hrTimeInZone_4` | float | Time in HR zone 4 |
| `hrTimeInZone_5` | float | Time in HR zone 5 |

### ActivityGPS
Per-point GPS and metrics during activities.

| Field | Type | Description |
|-------|------|-------------|
| `Activity_ID` | integer | Activity ID |
| `ActivityName` | string | Activity name |
| `Latitude` | float | GPS latitude |
| `Longitude` | float | GPS longitude |
| `Altitude` | float | Elevation (meters) |
| `Distance` | float | Cumulative distance |
| `Speed` | float | Current speed (m/s) |
| `GradeAdjustedSpeed` | float | Grade-adjusted pace |
| `HeartRate` | float | Heart rate at point |
| `Cadence` | integer | Steps/revolutions per minute |
| `Fractional_Cadence` | float | Fractional cadence |
| `Power` | integer | Power (watts) |
| `Accumulated_Power` | integer | Cumulative power |
| `Temperature` | integer | Temperature (°C) |
| `DurationSeconds` | float | Duration at point |
| `RunningEfficiency` | float | Running efficiency score |
| `VerticalOscillation` | float | Vertical oscillation (mm) |
| `StanceTime` | float | Ground contact time (ms) |
| `StanceTimePercent` | float | Ground contact time as % of stride |
| `StanceTimeBalance` | float | L/R ground contact balance (%) |
| `StepLength` | float | Step length (mm) |
| `VerticalRatio` | float | Vertical ratio (%) |

### ActivityLap
Per-lap metrics for activities.

| Field | Type | Description |
|-------|------|-------------|
| `Activity_ID` | integer | Activity ID |
| `ActivityName` | string | Activity name |
| `Index` | integer | Lap number |
| `Sport` | string | Sport type |
| `Distance` | float | Lap distance |
| `Elapsed_Time` | float | Lap time |
| `Calories` | integer | Lap calories |
| `Avg_HR` | integer | Average heart rate |
| `Max_HR` | integer | Maximum heart rate |
| `Avg_Speed` | float | Average speed |
| `Max_Speed` | float | Maximum speed |
| `Avg_Cadence` | integer | Average cadence |
| `Avg_Power` | integer | Average power |
| `Avg_Temperature` | integer | Average temperature |
| `Avg_VerticalOscillation` | float | Average vertical oscillation (mm) |
| `Avg_StanceTime` | float | Average ground contact time (ms) |
| `Avg_StanceTimePercent` | float | Average GCT as % of stride |
| `Avg_StanceTimeBalance` | float | Average L/R ground contact balance (%) |
| `Avg_StepLength` | float | Average step length (mm) |
| `Avg_VerticalRatio` | float | Average vertical ratio (%) |
| `Cycles` | integer | Cycles/steps in lap |

### ActivitySession
Activity session metadata.

| Field | Type | Description |
|-------|------|-------------|
| `Activity_ID` | integer | Activity ID |
| `ActivityName` | string | Activity name |
| `Index` | integer | Session index |
| `Sport` | string | Sport type |
| `Sub_Sport` | string | Sub-sport type |
| `Aerobic_Training` | float | Aerobic training effect |
| `Anaerobic_Training` | float | Anaerobic training effect |
| `Lengths` | integer | Pool lengths (swimming) |

---

## Body Metrics

### BodyComposition
Weight and body composition data.

| Field | Type | Description |
|-------|------|-------------|
| `weight` | float | Weight (grams) |

**Tags:** `Device`, `SourceType`, `Frequency`

---

## System

### DeviceSync
Device sync metadata.

| Field | Type | Description |
|-------|------|-------------|
| `Device_Name` | string | Device name |
| `imageUrl` | string | Device image URL |

### DemoPoint
Demo/test data point.

| Field | Type | Description |
|-------|------|-------------|
| `DemoField` | integer | Demo field |

---

## Example Queries

```sql
-- Daily steps for last 7 days
SELECT totalSteps FROM DailyStats WHERE time > now() - 7d

-- Heart rate on specific date
SELECT HeartRate FROM HeartRateIntraday
WHERE time >= '2026-01-10T00:00:00Z' AND time < '2026-01-11T00:00:00Z'

-- Sleep breakdown last 7 nights
SELECT sleepScore, deepSleepSeconds/60 as deepMin, remSleepSeconds/60 as remMin
FROM SleepSummary WHERE time > now() - 7d

-- Recent activities with distance
SELECT activityName, activityType, distance, calories, averageHR
FROM ActivitySummary ORDER BY time DESC LIMIT 10

-- Average resting HR by week
SELECT MEAN(restingHeartRate) FROM DailyStats
WHERE time > now() - 30d GROUP BY time(1w)
```

---

*Schema generated from InfluxDB GarminStats database, January 2026*
