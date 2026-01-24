"""Query builders for Garmin InfluxDB data with smart aggregation."""

import re
from datetime import datetime, timedelta
from typing import Literal

AggregationType = Literal["raw", "hourly", "daily", "weekly", "monthly", "auto"]


def parse_duration(duration: str) -> timedelta:
    """Parse duration string like '7d', '30d', '3m', '1y' into timedelta."""
    match = re.match(r"^(\d+)([dDwWmMyY])$", duration.strip())
    if not match:
        raise ValueError(f"Invalid duration format: {duration}. Use format like '7d', '30d', '3m', '1y'")

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "m":
        return timedelta(days=value * 30)  # Approximate
    elif unit == "y":
        return timedelta(days=value * 365)  # Approximate
    else:
        raise ValueError(f"Unknown duration unit: {unit}")


def get_time_range(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> tuple[datetime, datetime]:
    """
    Calculate time range from various input formats.

    Priority:
    1. If date is provided, return that single day
    2. If start_date/end_date provided, use those
    3. If duration provided (e.g., "7d"), calculate from now
    4. Default: last 7 days
    """
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if date:
        # Single day query
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1) - timedelta(seconds=1)
        return start, end

    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        return start, end

    if duration:
        delta = parse_duration(duration)
        end = now
        start = now - delta
        return start, end

    # Default: last 7 days
    return today - timedelta(days=7), now


def select_aggregation(start: datetime, end: datetime, aggregation: AggregationType = "auto") -> dict:
    """
    Select appropriate aggregation based on duration.

    Returns dict with:
    - aggregation: actual aggregation to use
    - group_by: InfluxQL GROUP BY time clause
    - description: human-readable description
    """
    if aggregation != "auto":
        # User-specified aggregation
        group_by_map = {
            "raw": None,
            "hourly": "1h",
            "daily": "1d",
            "weekly": "1w",
            "monthly": "30d",
        }
        return {
            "aggregation": aggregation,
            "group_by": group_by_map.get(aggregation),
            "description": f"User-specified {aggregation} aggregation",
        }

    # Auto-select based on duration
    duration = end - start
    days = duration.days

    if days <= 1:
        return {
            "aggregation": "raw",
            "group_by": None,
            "description": "Raw data (single day)",
        }
    elif days <= 7:
        return {
            "aggregation": "hourly",
            "group_by": "1h",
            "description": f"Hourly averages ({days} days)",
        }
    elif days <= 30:
        return {
            "aggregation": "daily",
            "group_by": "1d",
            "description": f"Daily values ({days} days)",
        }
    elif days <= 90:
        return {
            "aggregation": "daily",
            "group_by": "1d",
            "description": f"Daily values ({days} days)",
        }
    elif days <= 365:
        return {
            "aggregation": "weekly",
            "group_by": "1w",
            "description": f"Weekly averages ({days} days)",
        }
    else:
        return {
            "aggregation": "monthly",
            "group_by": "30d",
            "description": f"Monthly averages ({days} days)",
        }


def build_time_clause(start: datetime, end: datetime) -> str:
    """Build InfluxQL time clause."""
    return f"time >= '{start.isoformat()}Z' AND time <= '{end.isoformat()}Z'"


def build_select_query(
    measurement: str,
    fields: list[str] | str = "*",
    start: datetime | None = None,
    end: datetime | None = None,
    aggregation: AggregationType = "auto",
    where_extra: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> tuple[str, dict]:
    """
    Build an InfluxQL SELECT query with smart aggregation.

    Returns tuple of (query_string, aggregation_info).
    """
    if start is None or end is None:
        start, end = get_time_range()

    agg_info = select_aggregation(start, end, aggregation)

    # Build field selection
    if isinstance(fields, str):
        field_list = fields
    elif agg_info["group_by"] and fields != "*":
        # Apply aggregation functions to numeric fields
        field_list = ", ".join([f'MEAN("{f}") AS "{f}"' for f in fields])
    else:
        field_list = ", ".join([f'"{f}"' for f in fields]) if fields != "*" else "*"

    # Build query
    query = f'SELECT {field_list} FROM "{measurement}"'

    # Add WHERE clause
    time_clause = build_time_clause(start, end)
    where_parts = [time_clause]
    if where_extra:
        where_parts.append(where_extra)
    query += f" WHERE {' AND '.join(where_parts)}"

    # Add GROUP BY for aggregation
    if agg_info["group_by"]:
        query += f" GROUP BY time({agg_info['group_by']})"

    # Add ORDER BY
    if order_by:
        query += f" ORDER BY {order_by}"
    else:
        query += " ORDER BY time ASC"

    # Add LIMIT
    if limit:
        query += f" LIMIT {limit}"
    elif aggregation == "raw":
        # Safety limit for raw queries
        query += " LIMIT 5000"

    return query, agg_info


def build_daily_stats_query(
    start: datetime,
    end: datetime,
    fields: list[str] | None = None,
) -> str:
    """Build query for DailyStats measurement."""
    if fields is None:
        fields = [
            "totalSteps", "totalDistanceMeters", "restingHeartRate",
            "activeKilocalories", "bmrKilocalories",
            "bodyBatteryHighestValue", "bodyBatteryLowestValue",
            "stressPercentage", "averageSpo2",
        ]

    field_list = ", ".join([f'"{f}"' for f in fields])
    time_clause = build_time_clause(start, end)

    return f'SELECT {field_list} FROM "DailyStats" WHERE {time_clause} ORDER BY time ASC'


def build_sleep_query(start: datetime, end: datetime) -> str:
    """Build query for SleepSummary measurement."""
    fields = [
        "sleepScore", "sleepTimeSeconds", "deepSleepSeconds",
        "lightSleepSeconds", "remSleepSeconds", "awakeSleepSeconds",
        "awakeCount", "avgOvernightHrv", "avgSleepStress",
        "restingHeartRate", "averageRespirationValue",
    ]
    field_list = ", ".join([f'"{f}"' for f in fields])
    time_clause = build_time_clause(start, end)

    return f'SELECT {field_list} FROM "SleepSummary" WHERE {time_clause} ORDER BY time ASC'


def build_activities_query(
    start: datetime | None = None,
    end: datetime | None = None,
    activity_type: str | None = None,
    limit: int = 20,
) -> str:
    """Build query for ActivitySummary measurement."""
    fields = [
        "Activity_ID", "activityName", "activityType", "distance",
        "elapsedDuration", "movingDuration", "calories", "averageHR",
        "maxHR", "averageSpeed", "maxSpeed", "locationName",
    ]
    field_list = ", ".join([f'"{f}"' for f in fields])

    where_parts = []
    if start and end:
        where_parts.append(build_time_clause(start, end))
    if activity_type:
        where_parts.append(f"\"activityType\" = '{activity_type}'")

    query = f'SELECT {field_list} FROM "ActivitySummary"'
    if where_parts:
        query += f" WHERE {' AND '.join(where_parts)}"
    query += f" ORDER BY time DESC LIMIT {limit}"

    return query
