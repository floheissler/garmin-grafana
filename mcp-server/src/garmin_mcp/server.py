"""MCP Server for querying Garmin health data from InfluxDB."""

import json
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .db import db
from .queries import (
    AggregationType,
    build_activities_query,
    build_daily_stats_query,
    build_select_query,
    build_sleep_query,
    get_time_range,
)
from .formatters import (
    format_activities_list,
    format_body_composition,
    format_daily_summary,
    format_fitness_metrics,
    format_heart_rate_data,
    format_sleep_data,
    format_stress_body_battery,
)

# Initialize MCP server
mcp = FastMCP(
    "garmin-health",
    instructions="Query Garmin health and fitness data from InfluxDB. Use tools like get_daily_summary, get_sleep, get_heart_rate, get_activities to retrieve health metrics.",
)


@mcp.tool()
def get_daily_summary(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get daily health metrics summary (steps, heart rate, stress, etc.).

    Args:
        date: Single date in YYYY-MM-DD format (e.g., "2026-01-24")
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m", "1y" (from now)

    Returns:
        Daily metrics including steps, distance, resting HR, calories, body battery, stress.
        For multi-day queries, includes statistics and trends.

    Examples:
        - get_daily_summary(date="2026-01-24") - Single day
        - get_daily_summary(duration="7d") - Last 7 days
        - get_daily_summary(start_date="2026-01-01", end_date="2026-01-31") - January 2026
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query = build_daily_stats_query(start, end)
    data = db.query(query)
    result = format_daily_summary(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_sleep(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get sleep data including score, stages, HRV, and breathing rate.

    Args:
        date: Single date in YYYY-MM-DD format for that night's sleep
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d" (from now)

    Returns:
        Sleep score, duration, stage breakdown (deep/light/REM/awake),
        HRV, stress during sleep, and breathing rate.

    Examples:
        - get_sleep(date="2026-01-24") - Last night's sleep
        - get_sleep(duration="7d") - Last week's sleep data
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query = build_sleep_query(start, end)
    data = db.query(query)
    result = format_sleep_data(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_heart_rate(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get heart rate data with smart aggregation based on time range.

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m" (from now)
        aggregation: "auto" (default), "raw", "hourly", "daily", or "weekly"

    Returns:
        Heart rate data. Auto-aggregation:
        - 1 day: raw data (~720 points)
        - 2-7 days: hourly averages
        - 8-30 days: daily averages
        - 31+ days: weekly averages

    Examples:
        - get_heart_rate(date="2026-01-24") - Today's HR, raw
        - get_heart_rate(duration="30d") - Last month, daily averages
        - get_heart_rate(duration="7d", aggregation="raw") - Force raw data
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query, agg_info = build_select_query(
        measurement="HeartRateIntraday",
        fields=["HeartRate"],
        start=start,
        end=end,
        aggregation=aggregation,
    )
    data = db.query(query)
    result = format_heart_rate_data(data, agg_info)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_stress_body_battery(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get stress levels and body battery data with smart aggregation.

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d" (from now)
        aggregation: "auto" (default), "raw", "hourly", "daily", or "weekly"

    Returns:
        Stress levels (0-100, -1 during activity) and body battery (0-100).
        Auto-aggregates based on time range.

    Examples:
        - get_stress_body_battery(date="2026-01-24") - Today's data
        - get_stress_body_battery(duration="7d") - Last week
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query, agg_info = build_select_query(
        measurement="StressIntraday",
        fields=["stressLevel", "bodyBattery"],
        start=start,
        end=end,
        aggregation=aggregation,
    )
    data = db.query(query)
    result = format_stress_body_battery(data, agg_info)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_activities(
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    activity_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    Get list of activities/workouts with summary metrics.

    Args:
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "30d", "3m", "1y" (from now)
        activity_type: Filter by type (e.g., "running", "cycling", "swimming")
        limit: Maximum number of activities to return (default 20)

    Returns:
        List of activities with name, type, distance, duration, calories,
        heart rate, pace, and location.

    Examples:
        - get_activities(duration="30d") - Last month's activities
        - get_activities(activity_type="running", limit=10) - Last 10 runs
        - get_activities(start_date="2026-01-01", end_date="2026-01-31")
    """
    start, end = None, None
    if duration or (start_date and end_date):
        start, end = get_time_range(None, start_date, end_date, duration)

    query = build_activities_query(start, end, activity_type, limit)
    data = db.query(query)
    result = format_activities_list(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_trends(
    metric: Literal["steps", "resting_hr", "sleep_score", "hrv", "stress", "weight"],
    duration: str = "90d",
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get long-term trend analysis for a specific metric.

    Args:
        metric: One of "steps", "resting_hr", "sleep_score", "hrv", "stress", "weight"
        duration: Time period like "30d", "90d", "6m", "1y" (default "90d")
        aggregation: "auto" (default), "daily", "weekly", or "monthly"

    Returns:
        Trend analysis including min/max/avg, trend direction, and time series.

    Examples:
        - get_trends(metric="resting_hr", duration="90d") - 3-month HR trend
        - get_trends(metric="steps", duration="1y") - Yearly step trend
        - get_trends(metric="weight", duration="6m") - 6-month weight trend
    """
    start, end = get_time_range(duration=duration)

    # Map metric to measurement and field
    metric_map = {
        "steps": ("DailyStats", "totalSteps"),
        "resting_hr": ("DailyStats", "restingHeartRate"),
        "sleep_score": ("SleepSummary", "sleepScore"),
        "hrv": ("SleepSummary", "avgOvernightHrv"),
        "stress": ("DailyStats", "stressPercentage"),
        "weight": ("BodyComposition", "weight"),
    }

    if metric not in metric_map:
        return json.dumps({"error": f"Unknown metric: {metric}. Valid: {list(metric_map.keys())}"})

    measurement, field = metric_map[metric]

    # For daily measurements, always use daily aggregation at minimum
    if measurement in ("DailyStats", "SleepSummary", "BodyComposition"):
        query, agg_info = build_select_query(
            measurement=measurement,
            fields=[field],
            start=start,
            end=end,
            aggregation="raw",  # Already daily
        )
    else:
        query, agg_info = build_select_query(
            measurement=measurement,
            fields=[field],
            start=start,
            end=end,
            aggregation=aggregation,
        )

    data = db.query(query)

    if not data:
        return json.dumps({"error": f"No {metric} data available for the period"})

    values = [d.get(field) for d in data if d.get(field) is not None]

    # Special handling for weight (convert grams to kg)
    if metric == "weight":
        values = [v / 1000 for v in values]

    from .formatters import calculate_stats, calculate_trend, format_timestamp

    result = {
        "metric": metric,
        "period": {
            "start": format_timestamp(data[0].get("time", ""))[:10],
            "end": format_timestamp(data[-1].get("time", ""))[:10],
            "data_points": len(values),
        },
        "statistics": calculate_stats(values),
        "trend": calculate_trend(values),
        "data": [
            {
                "date": format_timestamp(d.get("time", ""))[:10],
                "value": round(d.get(field) / 1000, 1) if metric == "weight" else d.get(field),
            }
            for d in data if d.get(field) is not None
        ][:100],  # Limit output
    }

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_fitness_metrics() -> str:
    """
    Get current fitness metrics: VO2 max, fitness age, and race predictions.

    Returns:
        - VO2 max (ml/kg/min) with trend
        - Fitness age vs chronological age
        - Race predictions (5K, 10K, half marathon, marathon)

    Example:
        - get_fitness_metrics() - Current fitness snapshot
    """
    # Get recent data for each metric
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    start = now - timedelta(days=90)

    from .queries import build_time_clause

    time_clause = build_time_clause(start, now)

    vo2_query = f'SELECT "VO2_max_value" FROM "VO2_Max" WHERE {time_clause} ORDER BY time ASC'
    fitness_age_query = f'SELECT "fitnessAge", "chronologicalAge", "achievableFitnessAge" FROM "FitnessAge" WHERE {time_clause} ORDER BY time ASC'
    race_query = f'SELECT "time5K", "time10K", "timeHalfMarathon", "timeMarathon" FROM "RacePredictions" WHERE {time_clause} ORDER BY time ASC'

    vo2_data = db.query(vo2_query)
    fitness_age_data = db.query(fitness_age_query)
    race_data = db.query(race_query)

    result = format_fitness_metrics(vo2_data, fitness_age_data, race_data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_body_composition(
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get body composition data (weight tracking).

    Args:
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "30d", "90d", "6m" (from now)

    Returns:
        Weight readings in kg with trend analysis.

    Examples:
        - get_body_composition(duration="30d") - Last month
        - get_body_composition(duration="6m") - Last 6 months
    """
    start, end = get_time_range(None, start_date, end_date, duration or "90d")

    from .queries import build_time_clause

    time_clause = build_time_clause(start, end)
    query = f'SELECT "weight" FROM "BodyComposition" WHERE {time_clause} ORDER BY time ASC'

    data = db.query(query)
    result = format_body_composition(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def query_measurement(
    measurement: str,
    fields: str = "*",
    duration: str = "7d",
    aggregation: AggregationType = "auto",
    where_clause: str | None = None,
    limit: int = 1000,
) -> str:
    """
    Advanced: Query any InfluxDB measurement directly.

    Args:
        measurement: Measurement name (e.g., "HeartRateIntraday", "SleepIntraday")
        fields: Comma-separated field names or "*" for all
        duration: Time period like "7d", "30d", "3m"
        aggregation: "auto", "raw", "hourly", "daily", "weekly"
        where_clause: Additional WHERE conditions (e.g., "activityType = 'running'")
        limit: Maximum rows to return (default 1000)

    Returns:
        Raw query results as JSON.

    Available measurements:
        - DailyStats, SleepSummary, SleepIntraday
        - HeartRateIntraday, StepsIntraday, StressIntraday
        - BodyBatteryIntraday, BreathingRateIntraday, HRV_Intraday
        - ActivitySummary, ActivityGPS, ActivityLap
        - BodyComposition, VO2_Max, FitnessAge, RacePredictions

    Examples:
        - query_measurement(measurement="StepsIntraday", duration="1d")
        - query_measurement(measurement="ActivityGPS", where_clause="Activity_ID = 12345")
    """
    start, end = get_time_range(duration=duration)

    field_list = [f.strip() for f in fields.split(",")] if fields != "*" else "*"

    query, agg_info = build_select_query(
        measurement=measurement,
        fields=field_list,
        start=start,
        end=end,
        aggregation=aggregation,
        where_extra=where_clause,
        limit=limit,
    )

    data = db.query(query)

    result = {
        "measurement": measurement,
        "query": query,
        "aggregation": agg_info.get("description"),
        "row_count": len(data),
        "data": data[:100] if len(data) > 100 else data,
        "truncated": len(data) > 100,
    }

    return json.dumps(result, indent=2, default=str)


# Resources for schema discovery
@mcp.resource("garmin://schema/measurements")
def get_schema_measurements() -> str:
    """List all available measurements in the database."""
    measurements = db.get_measurements()
    return json.dumps({"measurements": measurements}, indent=2)


@mcp.resource("garmin://schema/{measurement}")
def get_schema_fields(measurement: str) -> str:
    """Get field definitions for a specific measurement."""
    fields = db.get_field_keys(measurement)
    return json.dumps({"measurement": measurement, "fields": fields}, indent=2)


@mcp.resource("garmin://status")
def get_status() -> str:
    """Get database connection status and last sync time."""
    try:
        connected = db.test_connection()

        # Get last data point
        last_sync = db.query('SELECT * FROM "DailyStats" ORDER BY time DESC LIMIT 1')
        last_time = last_sync[0].get("time") if last_sync else None

        return json.dumps({
            "connected": connected,
            "database": db.database,
            "host": db.host,
            "last_data": last_time,
        }, indent=2)
    except Exception as e:
        return json.dumps({"connected": False, "error": str(e)}, indent=2)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
