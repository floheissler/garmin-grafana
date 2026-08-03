"""Health regime classification using momentum indicators on biomarker data.

Computes rolling percentile rank, MACD, and RSI on resting heart rate,
overnight HRV, and sleep stress to classify current health trajectory
into regimes (Thriving, Improving, Stable, Strained, Critical, etc.).

Parameters were empirically optimized via grid search on 307 days of data
with predictive validity measured at 7/14/21-day horizons.
"""

from datetime import datetime, timedelta
from statistics import stdev

from .db import db
from .queries import build_time_clause

METRIC_CONFIG = {
    "resting_hr": {
        "measurement": "DailyStats",
        "field": "restingHeartRate",
        "label": "Resting Heart Rate",
        "unit": "bpm",
        "inverted": True,
        "macd": {"fast": 19, "slow": 47, "signal": 13},
        "rsi": {"period": 7, "upper": 70, "lower": 30},
    },
    "overnight_hrv": {
        "measurement": "SleepSummary",
        "field": "avgOvernightHrv",
        "label": "Overnight HRV",
        "unit": "ms",
        "inverted": False,
        "macd": {"fast": 19, "slow": 50, "signal": 13},
        "rsi": {"period": 7, "upper": 70, "lower": 30},
    },
    "sleep_stress": {
        "measurement": "SleepSummary",
        "field": "avgSleepStress",
        "label": "Sleep Stress",
        "unit": "",
        "inverted": True,
        "macd": {"fast": 11, "slow": 26, "signal": 11},
        "rsi": {"period": 14, "upper": 60, "lower": 40},
    },
}

PERCENTILE_BASELINE = (25, 75)
PERCENTILE_EXTREME = (10, 90)
MACD_STABLE_FACTOR = 0.03
LOOKBACK_DAYS = 200
MIN_DATA_POINTS = 30

FAVORABLE_REGIMES = {"Thriving", "Improving", "Recovering", "Rebounding", "Uptick"}
UNFAVORABLE_REGIMES = {"Peaking", "Fading", "Strained", "Critical", "Downtick"}


# ---------------------------------------------------------------------------
# Indicator computation (pure Python, no external dependencies)
# ---------------------------------------------------------------------------

def compute_ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average with SMA seed."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    sma = sum(values[:period]) / period
    result = [0.0] * (period - 1) + [sma]
    for i in range(period, len(values)):
        result.append(values[i] * k + result[-1] * (1 - k))
    return result


def compute_macd(
    values: list[float], fast: int, slow: int, signal: int
) -> dict | None:
    """MACD with configurable fast/slow/signal periods. Returns latest values."""
    if len(values) < slow + signal:
        return None
    ema_fast = compute_ema(values, fast)
    ema_slow = compute_ema(values, slow)
    if not ema_fast or not ema_slow:
        return None
    offset = slow - 1
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(offset, len(ema_slow))]
    if len(macd_line) < signal:
        return None
    signal_line = compute_ema(macd_line, signal)
    if not signal_line:
        return None
    sig_offset = signal - 1
    histogram = [
        macd_line[sig_offset + i] - signal_line[sig_offset + i]
        for i in range(len(signal_line) - sig_offset)
    ]
    return {
        "macd_line": macd_line[-1],
        "signal_line": signal_line[-1],
        "histogram": histogram[-1],
    }


def compute_rsi(values: list[float], period: int) -> float | None:
    """RSI using Wilder's smoothing. Returns latest value."""
    if len(values) < period + 1:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0.0) for d in deltas[:period]]
    losses = [max(-d, 0.0) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    alpha = 1.0 / period
    for d in deltas[period:]:
        avg_gain = avg_gain * (1 - alpha) + max(d, 0.0) * alpha
        avg_loss = avg_loss * (1 - alpha) + max(-d, 0.0) * alpha
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_percentile_rank(values: list[float], current: float) -> float:
    """Percentile rank of current value within the distribution (0-100)."""
    n = len(values)
    if n == 0:
        return 50.0
    below = sum(1 for v in values if v < current)
    return below / n * 100.0


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

def classify_position(percentile: float, inverted: bool) -> tuple[str, str]:
    """Map percentile to (position, direction) accounting for metric polarity.

    Returns:
        (position, direction) where position is baseline/displaced/extreme
        and direction is favorable/unfavorable/neutral.
    """
    lo_base, hi_base = PERCENTILE_BASELINE
    lo_ext, hi_ext = PERCENTILE_EXTREME

    if lo_base <= percentile <= hi_base:
        return "baseline", "neutral"

    if inverted:
        is_unfavorable = percentile > hi_base
    else:
        is_unfavorable = percentile < lo_base

    if is_unfavorable:
        threshold = hi_ext if inverted else lo_ext
        extreme = (percentile > threshold) if inverted else (percentile < threshold)
        position = "extreme" if extreme else "displaced"
        return position, "unfavorable"
    else:
        threshold = lo_ext if inverted else hi_ext
        extreme = (percentile < threshold) if inverted else (percentile > threshold)
        position = "extreme" if extreme else "displaced"
        return position, "favorable"


def classify_macd_direction(
    histogram: float, metric_std: float, inverted: bool
) -> str:
    """Classify MACD histogram into favorable/unfavorable/stable."""
    if abs(histogram) < MACD_STABLE_FACTOR * metric_std:
        return "stable"
    if inverted:
        return "unfavorable" if histogram > 0 else "favorable"
    return "favorable" if histogram > 0 else "unfavorable"


def classify_rsi_state(
    rsi: float, upper: float, lower: float, inverted: bool
) -> str:
    """Classify RSI into neutral or extreme state."""
    if inverted:
        if rsi >= upper:
            return "extreme_unfavorable"
        if rsi <= lower:
            return "extreme_favorable"
    else:
        if rsi >= upper:
            return "extreme_favorable"
        if rsi <= lower:
            return "extreme_unfavorable"
    return "neutral"


def classify_regime(position: str, direction: str, macd_dir: str) -> str:
    """Apply the regime classification matrix."""
    if position == "baseline":
        if macd_dir == "stable":
            return "Stable"
        return "Uptick" if macd_dir == "favorable" else "Downtick"

    effective_macd = macd_dir if macd_dir != "stable" else "unfavorable"

    matrix = {
        ("extreme", "favorable", "favorable"): "Thriving",
        ("extreme", "favorable", "unfavorable"): "Peaking",
        ("displaced", "favorable", "favorable"): "Improving",
        ("displaced", "favorable", "unfavorable"): "Fading",
        ("displaced", "unfavorable", "favorable"): "Recovering",
        ("displaced", "unfavorable", "unfavorable"): "Strained",
        ("extreme", "unfavorable", "favorable"): "Rebounding",
        ("extreme", "unfavorable", "unfavorable"): "Critical",
    }
    return matrix.get((position, direction, effective_macd), "Stable")


def assess_confluence(metric_results: dict) -> dict:
    """Compute overall assessment from per-metric regimes."""
    valid = {k: v for k, v in metric_results.items() if "regime" in v}
    if not valid:
        return {"assessment": "Insufficient Data", "favorable": 0, "unfavorable": 0}

    n_fav = sum(1 for v in valid.values() if v["regime"] in FAVORABLE_REGIMES)
    n_unfav = sum(1 for v in valid.values() if v["regime"] in UNFAVORABLE_REGIMES)
    total = len(valid)

    if n_fav == total:
        assessment = "Recovery Phase"
    elif n_fav >= 2 and n_unfav == 0:
        assessment = "Mostly Favorable"
    elif n_unfav == total:
        assessment = "Stress Accumulation"
    elif n_unfav >= 2:
        assessment = "Building Stress"
    elif n_fav >= 2:
        assessment = "Mostly Favorable"
    else:
        assessment = "Neutral"

    parts = []
    if n_fav:
        parts.append(f"{n_fav} favorable")
    neutral = total - n_fav - n_unfav
    if neutral:
        parts.append(f"{neutral} neutral")
    if n_unfav:
        parts.append(f"{n_unfav} unfavorable")

    return {
        "assessment": assessment,
        "favorable": n_fav,
        "unfavorable": n_unfav,
        "summary": f"{' / '.join(parts)} of {total} biomarkers",
    }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def _fetch_metric_series(
    measurement: str, field: str, start: datetime, end: datetime
) -> list[tuple[str, float]]:
    """Fetch a single field as (date_str, value) pairs."""
    time_clause = build_time_clause(start, end)
    query = (
        f'SELECT "{field}" FROM "{measurement}" '
        f"WHERE {time_clause} ORDER BY time ASC"
    )
    rows = db.query(query)
    result = []
    for row in rows:
        val = row.get(field)
        if val is not None:
            result.append((row["time"][:10], float(val)))
    return result


def _analyze_metric(key: str, series: list[tuple[str, float]]) -> dict:
    """Compute all indicators and classify regime for one metric."""
    cfg = METRIC_CONFIG[key]
    values = [v for _, v in series]

    if len(values) < MIN_DATA_POINTS:
        return {
            "value": values[-1] if values else None,
            "unit": cfg["unit"],
            "data_quality": "insufficient",
            "data_points": len(values),
            "regime": "Insufficient Data",
        }

    current = values[-1]
    metric_std = stdev(values) if len(values) >= 2 else 1.0

    pctl = compute_percentile_rank(values[:-1], current)
    position, direction = classify_position(pctl, cfg["inverted"])

    macd_cfg = cfg["macd"]
    macd_result = compute_macd(values, macd_cfg["fast"], macd_cfg["slow"], macd_cfg["signal"])

    rsi_cfg = cfg["rsi"]
    rsi_val = compute_rsi(values, rsi_cfg["period"])

    if macd_result:
        macd_dir = classify_macd_direction(macd_result["histogram"], metric_std, cfg["inverted"])
        histogram_val = round(macd_result["histogram"], 3)
    else:
        macd_dir = "stable"
        histogram_val = 0.0

    rsi_state = "neutral"
    if rsi_val is not None:
        rsi_state = classify_rsi_state(rsi_val, rsi_cfg["upper"], rsi_cfg["lower"], cfg["inverted"])

    regime = classify_regime(position, direction, macd_dir)

    result = {
        "value": round(current, 1),
        "unit": cfg["unit"],
        "percentile": round(pctl, 1),
        "position": position if direction == "neutral" else f"{position}_{direction}",
        "macd": {
            "direction": macd_dir,
            "histogram": histogram_val,
        },
        "rsi": {
            "value": round(rsi_val, 1) if rsi_val is not None else None,
            "state": rsi_state,
        },
        "regime": regime,
    }

    if rsi_state != "neutral":
        label = cfg["label"]
        if rsi_state == "extreme_unfavorable":
            result["rsi"]["alert"] = f"{label} at statistically extreme level — mean reversion expected (95%+ historical accuracy)"
        else:
            result["rsi"]["alert"] = f"{label} at favorable extreme — expect regression toward baseline"

    return result


def compute_health_regime(date_str: str | None = None) -> dict:
    """Compute the full health regime snapshot.

    Args:
        date_str: Target date as YYYY-MM-DD, or None for today.

    Returns:
        Structured dict with confluence assessment, per-metric regimes, and alerts.
    """
    if date_str:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return {"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD."}
    else:
        target = datetime.utcnow()

    target_end = target.replace(hour=23, minute=59, second=59)
    start = target - timedelta(days=LOOKBACK_DAYS)

    daily_series = _fetch_metric_series("DailyStats", "restingHeartRate", start, target_end)

    time_clause = build_time_clause(start, target_end)
    sleep_query = (
        f'SELECT "avgOvernightHrv", "avgSleepStress" FROM "SleepSummary" '
        f"WHERE {time_clause} ORDER BY time ASC"
    )
    sleep_rows = db.query(sleep_query)
    hrv_series = [(r["time"][:10], float(r["avgOvernightHrv"])) for r in sleep_rows if r.get("avgOvernightHrv") is not None]
    stress_series = [(r["time"][:10], float(r["avgSleepStress"])) for r in sleep_rows if r.get("avgSleepStress") is not None]

    metric_results = {
        "resting_hr": _analyze_metric("resting_hr", daily_series),
        "overnight_hrv": _analyze_metric("overnight_hrv", hrv_series),
        "sleep_stress": _analyze_metric("sleep_stress", stress_series),
    }

    confluence = assess_confluence(metric_results)

    alerts = []
    for key, result in metric_results.items():
        if result.get("regime") == "Critical":
            cfg = METRIC_CONFIG[key]
            alerts.append({
                "metric": key,
                "type": "critical_regime",
                "message": f"{cfg['label']} significantly displaced and still worsening",
            })
        rsi_alert = result.get("rsi", {}).get("alert")
        if rsi_alert:
            alerts.append({
                "metric": key,
                "type": "rsi_extreme",
                "message": rsi_alert,
            })

    first_date = None
    for series in [daily_series, hrv_series, stress_series]:
        if series:
            d = series[0][0]
            if first_date is None or d < first_date:
                first_date = d

    return {
        "snapshot_date": target.strftime("%Y-%m-%d"),
        "data_period": {
            "start": first_date or start.strftime("%Y-%m-%d"),
            "end": target.strftime("%Y-%m-%d"),
            "days": len(daily_series),
        },
        "confluence": confluence,
        "metrics": metric_results,
        "alerts": alerts,
    }
