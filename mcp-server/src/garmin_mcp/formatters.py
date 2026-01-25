"""LLM-friendly output formatters for Garmin data."""

from datetime import datetime
from typing import Any


def format_duration_seconds(seconds: float | int | None) -> str:
    """Format seconds into human-readable duration."""
    if seconds is None:
        return "N/A"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_distance_meters(meters: float | int | None) -> str:
    """Format meters into human-readable distance."""
    if meters is None:
        return "N/A"

    if meters >= 1000:
        return f"{meters / 1000:.2f} km"
    else:
        return f"{int(meters)} m"


def format_pace_mps(speed_mps: float | None) -> str:
    """Convert m/s to min/km pace."""
    if speed_mps is None or speed_mps == 0:
        return "N/A"

    # m/s to min/km: (1000 / speed_mps) / 60
    pace_minutes = (1000 / speed_mps) / 60
    mins = int(pace_minutes)
    secs = int((pace_minutes - mins) * 60)
    return f"{mins}:{secs:02d} /km"


def format_timestamp(ts: str | datetime) -> str:
    """Format timestamp for display."""
    if isinstance(ts, str):
        # Parse ISO format
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    else:
        dt = ts

    return dt.strftime("%Y-%m-%d %H:%M")


def calculate_stats(values: list[float | int]) -> dict[str, float | None]:
    """Calculate basic statistics for a list of values."""
    if not values:
        return {"min": None, "max": None, "avg": None, "count": 0}

    clean_values = [v for v in values if v is not None]
    if not clean_values:
        return {"min": None, "max": None, "avg": None, "count": 0}

    return {
        "min": min(clean_values),
        "max": max(clean_values),
        "avg": round(sum(clean_values) / len(clean_values), 1),
        "count": len(clean_values),
    }


def calculate_trend(values: list[float | int]) -> str:
    """Determine trend direction from a list of values."""
    if len(values) < 2:
        return "insufficient data"

    clean_values = [v for v in values if v is not None]
    if len(clean_values) < 2:
        return "insufficient data"

    # Compare first and last third averages
    third = len(clean_values) // 3
    if third == 0:
        first_avg = clean_values[0]
        last_avg = clean_values[-1]
    else:
        first_avg = sum(clean_values[:third]) / third
        last_avg = sum(clean_values[-third:]) / third

    diff_pct = ((last_avg - first_avg) / first_avg) * 100 if first_avg != 0 else 0

    if diff_pct > 5:
        return f"increasing (+{diff_pct:.1f}%)"
    elif diff_pct < -5:
        return f"decreasing ({diff_pct:.1f}%)"
    else:
        return "stable"


def format_daily_summary(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Format daily stats data for LLM consumption."""
    if not data:
        return {"error": "No data available"}

    if len(data) == 1:
        # Single day
        day = data[0]
        return {
            "date": format_timestamp(day.get("time", "")),
            "steps": day.get("totalSteps"),
            "distance": format_distance_meters(day.get("totalDistanceMeters")),
            "resting_hr": day.get("restingHeartRate"),
            "active_calories": round(day.get("activeKilocalories", 0) or 0),
            "total_calories": round((day.get("activeKilocalories") or 0) + (day.get("bmrKilocalories") or 0)),
            "body_battery": {
                "high": day.get("bodyBatteryHighestValue"),
                "low": day.get("bodyBatteryLowestValue"),
            },
            "stress_pct": day.get("stressPercentage"),
            "spo2_avg": day.get("averageSpo2"),
        }

    # Multiple days - provide summary
    steps = [d.get("totalSteps") for d in data if d.get("totalSteps")]
    rhr = [d.get("restingHeartRate") for d in data if d.get("restingHeartRate")]

    return {
        "period": {
            "start": format_timestamp(data[0].get("time", "")),
            "end": format_timestamp(data[-1].get("time", "")),
            "days": len(data),
        },
        "steps": {
            **calculate_stats(steps),
            "total": sum(s for s in steps if s),
            "trend": calculate_trend(steps),
        },
        "resting_hr": {
            **calculate_stats(rhr),
            "trend": calculate_trend(rhr),
        },
        "daily_breakdown": [
            {
                "date": format_timestamp(d.get("time", ""))[:10],
                "steps": d.get("totalSteps"),
                "resting_hr": d.get("restingHeartRate"),
                "stress_pct": d.get("stressPercentage"),
            }
            for d in data
        ],
    }


def format_sleep_data(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Format sleep data for LLM consumption."""
    if not data:
        return {"error": "No sleep data available"}

    if len(data) == 1:
        sleep = data[0]
        total_sleep_sec = sleep.get("sleepTimeSeconds", 0) or 0

        return {
            "date": format_timestamp(sleep.get("time", ""))[:10],
            "score": sleep.get("sleepScore"),
            "duration": format_duration_seconds(total_sleep_sec),
            "stages": {
                "deep": format_duration_seconds(sleep.get("deepSleepSeconds")),
                "light": format_duration_seconds(sleep.get("lightSleepSeconds")),
                "rem": format_duration_seconds(sleep.get("remSleepSeconds")),
                "awake": format_duration_seconds(sleep.get("awakeSleepSeconds")),
            },
            "stage_percentages": {
                "deep": round((sleep.get("deepSleepSeconds") or 0) / total_sleep_sec * 100, 1) if total_sleep_sec else 0,
                "light": round((sleep.get("lightSleepSeconds") or 0) / total_sleep_sec * 100, 1) if total_sleep_sec else 0,
                "rem": round((sleep.get("remSleepSeconds") or 0) / total_sleep_sec * 100, 1) if total_sleep_sec else 0,
            },
            "awake_count": sleep.get("awakeCount"),
            "hrv_avg": sleep.get("avgOvernightHrv"),
            "stress_avg": sleep.get("avgSleepStress"),
            "resting_hr": sleep.get("restingHeartRate"),
            "breathing_rate": sleep.get("averageRespirationValue"),
        }

    # Multiple nights
    scores = [d.get("sleepScore") for d in data if d.get("sleepScore")]
    durations = [d.get("sleepTimeSeconds") for d in data if d.get("sleepTimeSeconds")]
    hrvs = [d.get("avgOvernightHrv") for d in data if d.get("avgOvernightHrv")]

    return {
        "period": {
            "start": format_timestamp(data[0].get("time", ""))[:10],
            "end": format_timestamp(data[-1].get("time", ""))[:10],
            "nights": len(data),
        },
        "score": {
            **calculate_stats(scores),
            "trend": calculate_trend(scores),
        },
        "duration": {
            **calculate_stats(durations),
            "avg_formatted": format_duration_seconds(calculate_stats(durations)["avg"]),
        },
        "hrv": {
            **calculate_stats(hrvs),
            "trend": calculate_trend(hrvs),
        },
        "nightly_breakdown": [
            {
                "date": format_timestamp(d.get("time", ""))[:10],
                "score": d.get("sleepScore"),
                "duration": format_duration_seconds(d.get("sleepTimeSeconds")),
                "hrv": d.get("avgOvernightHrv"),
            }
            for d in data
        ],
    }


def format_heart_rate_data(data: list[dict[str, Any]], aggregation_info: dict) -> dict[str, Any]:
    """Format heart rate data for LLM consumption."""
    if not data:
        return {"error": "No heart rate data available"}

    hr_values = [d.get("HeartRate") for d in data if d.get("HeartRate")]

    result = {
        "aggregation": aggregation_info.get("description", "raw"),
        "data_points": len(data),
        "statistics": calculate_stats(hr_values),
    }

    # Include time series for reasonable sizes
    if len(data) <= 50:
        result["readings"] = [
            {
                "time": format_timestamp(d.get("time", "")),
                "hr": d.get("HeartRate"),
            }
            for d in data if d.get("HeartRate")
        ]
    else:
        # Summarize by providing key points
        result["sample_readings"] = [
            {
                "time": format_timestamp(data[i].get("time", "")),
                "hr": data[i].get("HeartRate"),
            }
            for i in range(0, len(data), max(1, len(data) // 20))
            if data[i].get("HeartRate")
        ]

    return result


def format_stress_body_battery(data: list[dict[str, Any]], aggregation_info: dict) -> dict[str, Any]:
    """Format stress and body battery data for LLM consumption."""
    if not data:
        return {"error": "No stress/body battery data available"}

    stress_values = [d.get("stressLevel") for d in data if d.get("stressLevel") is not None and d.get("stressLevel") >= 0]
    bb_values = [d.get("bodyBattery") for d in data if d.get("bodyBattery") is not None]

    result = {
        "aggregation": aggregation_info.get("description", "raw"),
        "data_points": len(data),
        "stress": calculate_stats(stress_values),
        "body_battery": calculate_stats(bb_values),
    }

    if len(data) <= 50:
        result["readings"] = [
            {
                "time": format_timestamp(d.get("time", "")),
                "stress": d.get("stressLevel") if d.get("stressLevel", -1) >= 0 else "activity",
                "body_battery": d.get("bodyBattery"),
            }
            for d in data
        ]

    return result


def format_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """Format a single activity for LLM consumption."""
    return {
        "id": activity.get("Activity_ID"),
        "name": activity.get("activityName"),
        "type": activity.get("activityType"),
        "date": format_timestamp(activity.get("time", "")),
        "distance": format_distance_meters(activity.get("distance")),
        "duration": format_duration_seconds(activity.get("elapsedDuration")),
        "moving_time": format_duration_seconds(activity.get("movingDuration")),
        "calories": round(activity.get("calories", 0) or 0),
        "heart_rate": {
            "avg": activity.get("averageHR"),
            "max": activity.get("maxHR"),
        },
        "pace": format_pace_mps(activity.get("averageSpeed")),
        "location": activity.get("locationName"),
    }


def format_activities_list(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Format activities list for LLM consumption."""
    if not data:
        return {"error": "No activities found", "activities": []}

    return {
        "count": len(data),
        "activities": [format_activity(a) for a in data],
    }


def format_fitness_metrics(
    vo2_max: list[dict] | None = None,
    fitness_age: list[dict] | None = None,
    race_predictions: list[dict] | None = None,
) -> dict[str, Any]:
    """Format fitness metrics for LLM consumption."""
    result = {}

    if vo2_max and len(vo2_max) > 0:
        latest = vo2_max[-1]
        values = [d.get("VO2_max_value") for d in vo2_max if d.get("VO2_max_value")]
        result["vo2_max"] = {
            "current": latest.get("VO2_max_value"),
            "date": format_timestamp(latest.get("time", ""))[:10],
            "trend": calculate_trend(values) if len(values) > 1 else "single reading",
        }

    if fitness_age and len(fitness_age) > 0:
        latest = fitness_age[-1]
        result["fitness_age"] = {
            "current": latest.get("fitnessAge"),
            "chronological_age": latest.get("chronologicalAge"),
            "achievable": latest.get("achievableFitnessAge"),
            "date": format_timestamp(latest.get("time", ""))[:10],
        }

    if race_predictions and len(race_predictions) > 0:
        latest = race_predictions[-1]
        result["race_predictions"] = {
            "date": format_timestamp(latest.get("time", ""))[:10],
            "5k": format_duration_seconds(latest.get("time5K")),
            "10k": format_duration_seconds(latest.get("time10K")),
            "half_marathon": format_duration_seconds(latest.get("timeHalfMarathon")),
            "marathon": format_duration_seconds(latest.get("timeMarathon")),
        }

    if not result:
        return {"error": "No fitness metrics available"}

    return result


def format_hrv_data(
    daily_data: list[dict[str, Any]],
    intraday_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Format HRV data for LLM consumption."""
    if not daily_data and not intraday_data:
        return {"error": "No HRV data available"}

    result = {}

    # Daily/nightly HRV from sleep
    if daily_data:
        hrvs = [d.get("avgOvernightHrv") for d in daily_data if d.get("avgOvernightHrv")]

        if len(daily_data) == 1:
            result["overnight"] = {
                "date": format_timestamp(daily_data[0].get("time", ""))[:10],
                "avg_hrv": daily_data[0].get("avgOvernightHrv"),
                "resting_hr": daily_data[0].get("restingHeartRate"),
                "sleep_score": daily_data[0].get("sleepScore"),
            }
        else:
            result["overnight"] = {
                "period": {
                    "start": format_timestamp(daily_data[0].get("time", ""))[:10],
                    "end": format_timestamp(daily_data[-1].get("time", ""))[:10],
                    "nights": len(daily_data),
                },
                "statistics": calculate_stats(hrvs),
                "trend": calculate_trend(hrvs),
                "nightly_values": [
                    {
                        "date": format_timestamp(d.get("time", ""))[:10],
                        "hrv": d.get("avgOvernightHrv"),
                        "resting_hr": d.get("restingHeartRate"),
                    }
                    for d in daily_data
                ],
            }

    # Intraday HRV readings (during sleep)
    if intraday_data:
        hrv_values = [d.get("hrvValue") for d in intraday_data if d.get("hrvValue")]
        result["intraday"] = {
            "readings": len(intraday_data),
            "statistics": calculate_stats(hrv_values),
        }
        # Include readings if not too many
        if len(intraday_data) <= 100:
            result["intraday"]["values"] = [
                {
                    "time": format_timestamp(d.get("time", "")),
                    "hrv": d.get("hrvValue"),
                }
                for d in intraday_data if d.get("hrvValue")
            ]

    return result


def format_activity_details(
    summary: dict[str, Any],
    laps: list[dict[str, Any]] | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format comprehensive activity details for LLM consumption."""
    if not summary:
        return {"error": "Activity not found"}

    # Basic info
    result = {
        "id": summary.get("Activity_ID"),
        "name": summary.get("activityName"),
        "type": summary.get("activityType"),
        "date": format_timestamp(summary.get("time", "")),
        "location": summary.get("locationName"),
    }

    # Distance and duration
    result["distance"] = {
        "value": format_distance_meters(summary.get("distance")),
        "meters": summary.get("distance"),
    }
    result["duration"] = {
        "elapsed": format_duration_seconds(summary.get("elapsedDuration")),
        "moving": format_duration_seconds(summary.get("movingDuration")),
        "elapsed_seconds": summary.get("elapsedDuration"),
        "moving_seconds": summary.get("movingDuration"),
    }

    # Speed and pace
    avg_speed = summary.get("averageSpeed")
    max_speed = summary.get("maxSpeed")
    result["speed"] = {
        "avg_mps": round(avg_speed, 2) if avg_speed else None,
        "max_mps": round(max_speed, 2) if max_speed else None,
        "avg_pace": format_pace_mps(avg_speed),
        "max_pace": format_pace_mps(max_speed),
    }

    # Heart rate
    result["heart_rate"] = {
        "avg": summary.get("averageHR"),
        "max": summary.get("maxHR"),
    }

    # HR zones (if available)
    hr_zones = {}
    for i in range(1, 6):
        zone_time = summary.get(f"hrTimeInZone_{i}")
        if zone_time:
            hr_zones[f"zone_{i}"] = format_duration_seconds(zone_time)
    if hr_zones:
        result["heart_rate"]["zones"] = hr_zones

    # Calories
    result["calories"] = {
        "total": round(summary.get("calories", 0) or 0),
        "bmr": round(summary.get("bmrCalories", 0) or 0),
    }

    # Training effect from session
    if session:
        result["training_effect"] = {
            "aerobic": session.get("Aerobic_Training"),
            "anaerobic": session.get("Anaerobic_Training"),
        }
        if session.get("Sport"):
            result["sport"] = session.get("Sport")
        if session.get("Sub_Sport"):
            result["sub_sport"] = session.get("Sub_Sport")

    # Laps breakdown
    if laps:
        lap_details = []
        for i, lap in enumerate(laps):
            # Calculate pace from distance and time if Avg_Speed not available
            distance = lap.get("Distance")
            elapsed_time = lap.get("Elapsed_Time")
            avg_speed = lap.get("Avg_Speed")

            if not avg_speed and distance and elapsed_time and elapsed_time > 0:
                avg_speed = distance / elapsed_time  # m/s

            lap_details.append({
                "lap": lap.get("Index", i + 1),
                "distance": format_distance_meters(distance),
                "time": format_duration_seconds(elapsed_time),
                "pace": format_pace_mps(avg_speed),
                "avg_hr": lap.get("Avg_HR"),
                "max_hr": lap.get("Max_HR"),
                "cadence": lap.get("Avg_Cadence"),
                "power": lap.get("Avg_Power"),
                "calories": lap.get("Calories"),
            })

        result["laps"] = {
            "count": len(laps),
            "details": lap_details,
        }

        # Calculate lap statistics
        lap_hrs = [lap.get("Avg_HR") for lap in laps if lap.get("Avg_HR")]
        lap_cadences = [lap.get("Avg_Cadence") for lap in laps if lap.get("Avg_Cadence")]
        lap_powers = [lap.get("Avg_Power") for lap in laps if lap.get("Avg_Power")]

        if lap_cadences:
            result["cadence"] = calculate_stats(lap_cadences)
        if lap_powers:
            result["power"] = calculate_stats(lap_powers)

    return result


def format_body_composition(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Format body composition data for LLM consumption."""
    if not data:
        return {"error": "No body composition data available"}

    # Weight is stored in grams
    weights_kg = [d.get("weight") / 1000 for d in data if d.get("weight")]

    if len(data) == 1:
        return {
            "date": format_timestamp(data[0].get("time", ""))[:10],
            "weight_kg": round(weights_kg[0], 1) if weights_kg else None,
        }

    return {
        "period": {
            "start": format_timestamp(data[0].get("time", ""))[:10],
            "end": format_timestamp(data[-1].get("time", ""))[:10],
            "readings": len(data),
        },
        "weight_kg": {
            "current": round(weights_kg[-1], 1) if weights_kg else None,
            "min": round(min(weights_kg), 1) if weights_kg else None,
            "max": round(max(weights_kg), 1) if weights_kg else None,
            "change": round(weights_kg[-1] - weights_kg[0], 1) if len(weights_kg) >= 2 else None,
            "trend": calculate_trend(weights_kg),
        },
        "readings": [
            {
                "date": format_timestamp(d.get("time", ""))[:10],
                "weight_kg": round(d.get("weight", 0) / 1000, 1),
            }
            for d in data
        ],
    }
