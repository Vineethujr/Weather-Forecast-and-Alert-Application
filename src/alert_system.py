"""
Configurable Weather Alert System.
Evaluates current observations and forecast intervals against configurable thresholds.
Supports multi-hazard compound risk detection, severity classification (Advisory, Watch, Warning),
duplicate suppression, resilient null-handling, and mandatory non-official disclaimers.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Mandatory ethical and safety disclaimer
OFFICIAL_WARNING_DISCLAIMER = (
    "These are informational, rule-based application alerts and are not official meteorological warnings. "
    "Follow relevant government weather agencies and local authorities for safety instructions."
)


# ==============================================================================
# Configurable Thresholds Container
# ==============================================================================

@dataclass
class AlertThresholds:
    """Configurable alert threshold limits."""
    high_temp_c: float = 40.0
    high_humidity_pct: float = 85.0
    high_rain_prob_pct: float = 70.0
    high_wind_speed_kmh: float = 50.0

    @classmethod
    def from_env(cls) -> "AlertThresholds":
        """Loads alert thresholds from environment variables with safe fallbacks."""
        def _get_float_env(key: str, default: float) -> float:
            val = os.getenv(key)
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                logger.warning(f"Invalid value '{val}' for environment variable {key}. Using default: {default}")
                return default

        return cls(
            high_temp_c=_get_float_env("THRESHOLD_HIGH_TEMP_C", 40.0),
            high_humidity_pct=_get_float_env("THRESHOLD_HIGH_HUMIDITY_PCT", 85.0),
            high_rain_prob_pct=_get_float_env("THRESHOLD_HIGH_RAIN_PROB_PCT", 70.0),
            high_wind_speed_kmh=_get_float_env("THRESHOLD_HIGH_WIND_SPEED_KMH", 50.0),
        )


# ==============================================================================
# Severity Classification Logic
# ==============================================================================

def classify_severity(alert_type: str, measured: float, threshold: float) -> str:
    """
    Assigns an informational application severity tier:
    - Advisory: Condition slightly exceeds threshold (emerging concern).
    - Watch: Condition significantly exceeds threshold (moderate concern).
    - Warning: Condition severely exceeds threshold (critical hazard).

    Logic:
    - Temperature (Threshold T=40.0):
      T < val <= T+3.0  -> Advisory
      T+3.0 < val <= T+6.0 -> Watch
      val > T+6.0        -> Warning
    - Humidity (Threshold H=85.0):
      H < val <= 90.0    -> Advisory
      90.0 < val <= 95.0 -> Watch
      val > 95.0         -> Warning
    - Rain Probability (Threshold R=70.0):
      R < val <= 80.0    -> Advisory
      80.0 < val <= 90.0 -> Watch
      val > 90.0         -> Warning
    - Wind Speed (Threshold W=50.0):
      W < val <= 65.0    -> Advisory
      65.0 < val <= 85.0 -> Watch
      val > 85.0         -> Warning
    """
    if "Temperature" in alert_type:
        if measured > threshold + 6.0:
            return "Warning"
        elif measured > threshold + 3.0:
            return "Watch"
        return "Advisory"

    elif "Humidity" in alert_type:
        if measured > 95.0:
            return "Warning"
        elif measured > 90.0:
            return "Watch"
        return "Advisory"

    elif "Rain" in alert_type:
        if measured > 90.0:
            return "Warning"
        elif measured > 80.0:
            return "Watch"
        return "Advisory"

    elif "Wind" in alert_type:
        if measured > 85.0:
            return "Warning"
        elif measured > 65.0:
            return "Watch"
        return "Advisory"

    return "Advisory"


# ==============================================================================
# Single Condition Evaluator
# ==============================================================================

def evaluate_single_condition(
    alert_type: str,
    measured_value: Optional[float],
    threshold: float,
    unit: str,
    timestamp: Any,
    city: str,
    data_source: str,
    is_simulated: bool,
    context_label: str = "Observation"
) -> Optional[Dict[str, Any]]:
    """
    Evaluates whether a single numerical measurement breaches its threshold.
    
    Returns:
        Structured alert dict if breached, or None if normal or measurement is missing.
    """
    if measured_value is None or pd.isna(measured_value):
        return None

    try:
        val = float(measured_value)
    except (ValueError, TypeError):
        return None

    if val <= threshold:
        return None

    severity = classify_severity(alert_type, val, threshold)
    ts_str = str(timestamp) if timestamp is not None and not pd.isna(timestamp) else "Current Time"
    
    # Generate unique deterministic alert identifier
    safe_type = alert_type.lower().replace(" ", "_")
    safe_city = city.lower().replace(" ", "_")
    safe_time = ts_str.replace(":", "-").replace(" ", "_")
    alert_id = f"alert_{safe_type}_{safe_city}_{safe_time}"

    message = (
        f"[{severity.upper()}] {alert_type} for {city} at {ts_str}: "
        f"Measured {val:.1f} {unit} exceeds configurable threshold of {threshold:.1f} {unit} ({context_label})."
    )

    return {
        "alert_id": alert_id,
        "alert_type": alert_type,
        "severity": severity,
        "city": city,
        "message": message,
        "measured_value": round(val, 2),
        "threshold": round(threshold, 2),
        "unit": unit,
        "timestamp": ts_str,
        "context_label": context_label,
        "data_source": data_source,
        "is_simulated": is_simulated,
    }


# ==============================================================================
# Current Weather & Forecast Alert Evaluators
# ==============================================================================

def evaluate_current_weather_alerts(
    current_data: Optional[Dict[str, Any]],
    thresholds: Optional[AlertThresholds] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates current weather observations against alert thresholds.
    """
    if current_data is None or not isinstance(current_data, dict):
        return []

    if thresholds is None:
        thresholds = AlertThresholds.from_env()

    if metadata is None:
        metadata = {}

    city = current_data.get("city") or metadata.get("city", "Unknown City")
    data_source = current_data.get("data_source") or metadata.get("data_source", "UNKNOWN")
    is_simulated = current_data.get("is_simulated", metadata.get("is_simulated", False))
    ts = current_data.get("timestamp")

    alerts: List[Dict[str, Any]] = []

    # 1. Temperature Alert (> 40°C)
    t_alert = evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=current_data.get("temperature_c", current_data.get("temperature")),
        threshold=thresholds.high_temp_c,
        unit="°C",
        timestamp=ts,
        city=city,
        data_source=data_source,
        is_simulated=is_simulated,
        context_label="Current Observation"
    )
    if t_alert:
        alerts.append(t_alert)

    # 2. Humidity Alert (> 85%)
    h_alert = evaluate_single_condition(
        alert_type="High Humidity Alert",
        measured_value=current_data.get("humidity_pct", current_data.get("humidity")),
        threshold=thresholds.high_humidity_pct,
        unit="%",
        timestamp=ts,
        city=city,
        data_source=data_source,
        is_simulated=is_simulated,
        context_label="Current Observation"
    )
    if h_alert:
        alerts.append(h_alert)

    # 3. Rain Probability Alert (> 70%)
    r_alert = evaluate_single_condition(
        alert_type="Rain Alert",
        measured_value=current_data.get("rain_probability_pct", current_data.get("precipitation_probability")),
        threshold=thresholds.high_rain_prob_pct,
        unit="%",
        timestamp=ts,
        city=city,
        data_source=data_source,
        is_simulated=is_simulated,
        context_label="Current Observation"
    )
    if r_alert:
        alerts.append(r_alert)

    # 4. Wind Speed Alert (> 50 km/h)
    w_alert = evaluate_single_condition(
        alert_type="High Wind Alert",
        measured_value=current_data.get("wind_speed_kmh", current_data.get("wind_speed")),
        threshold=thresholds.high_wind_speed_kmh,
        unit="km/h",
        timestamp=ts,
        city=city,
        data_source=data_source,
        is_simulated=is_simulated,
        context_label="Current Observation"
    )
    if w_alert:
        alerts.append(w_alert)

    return alerts


def evaluate_forecast_alerts(
    forecast_df: Optional[pd.DataFrame],
    thresholds: Optional[AlertThresholds] = None,
    metadata: Optional[Dict[str, Any]] = None,
    seen_keys: Optional[Set[Tuple[str, str]]] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates every forecast interval in a Pandas DataFrame independently.
    Avoids duplicate alerts for the same condition and timestamp.
    """
    if forecast_df is None or not isinstance(forecast_df, pd.DataFrame) or forecast_df.empty:
        return []

    if thresholds is None:
        thresholds = AlertThresholds.from_env()

    if metadata is None:
        metadata = {}

    if seen_keys is None:
        seen_keys = set()

    city = metadata.get("city", "Unknown City")
    data_source = metadata.get("data_source", "UNKNOWN")
    is_simulated = metadata.get("is_simulated", False)

    alerts: List[Dict[str, Any]] = []

    for _, row in forecast_df.iterrows():
        ts = row.get("timestamp")
        ts_str = str(ts) if pd.notna(ts) else "Forecast Time"

        checks = [
            ("High Temperature Alert", row.get("temperature_c"), thresholds.high_temp_c, "°C"),
            ("High Humidity Alert", row.get("humidity_pct"), thresholds.high_humidity_pct, "%"),
            ("Rain Alert", row.get("rain_probability_pct"), thresholds.high_rain_prob_pct, "%"),
            ("High Wind Alert", row.get("wind_speed_kmh"), thresholds.high_wind_speed_kmh, "km/h"),
        ]

        for alert_type, val, thresh, unit in checks:
            key = (alert_type, ts_str)
            if key in seen_keys:
                continue

            alert = evaluate_single_condition(
                alert_type=alert_type,
                measured_value=val,
                threshold=thresh,
                unit=unit,
                timestamp=ts,
                city=city,
                data_source=data_source,
                is_simulated=is_simulated,
                context_label="Forecast Horizon"
            )
            if alert:
                alerts.append(alert)
                seen_keys.add(key)

    return alerts


# ==============================================================================
# Master Alert Engine Orchestrator
# ==============================================================================

def evaluate_weather_alerts(
    current_data: Optional[Dict[str, Any]],
    forecast_df: Optional[pd.DataFrame] = None,
    thresholds: Optional[AlertThresholds] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Master entry point for the Weather Alert Engine.
    
    Evaluates current weather observations and all forecast intervals against
    configurable alert thresholds. Detects compound multi-hazard conditions,
    suppresses duplicates, and attaches mandatory disclaimers.
    
    Args:
        current_data: Dictionary of current weather observations.
        forecast_df: Optional DataFrame of upcoming forecast intervals.
        thresholds: Configurable AlertThresholds instance.
        metadata: Top-level metadata dictionary (city, data_source, etc.).
        
    Returns:
        Structured alert report dictionary with full summary and provenance.
    """
    if thresholds is None:
        thresholds = AlertThresholds.from_env()

    if metadata is None:
        metadata = {}

    city = (current_data.get("city") if current_data else None) or metadata.get("city", "Unknown City")
    data_source = (current_data.get("data_source") if current_data else None) or metadata.get("data_source", "UNKNOWN")
    is_simulated = bool((current_data.get("is_simulated") if current_data else None) or metadata.get("is_simulated", False))

    seen_keys: Set[Tuple[str, str]] = set()

    # 1. Evaluate current observation alerts
    current_alerts = evaluate_current_weather_alerts(
        current_data=current_data,
        thresholds=thresholds,
        metadata=metadata
    )
    for ca in current_alerts:
        seen_keys.add((ca["alert_type"], str(ca["timestamp"])))

    # 2. Evaluate forecast horizon alerts
    forecast_alerts = evaluate_forecast_alerts(
        forecast_df=forecast_df,
        thresholds=thresholds,
        metadata=metadata,
        seen_keys=seen_keys
    )

    all_alerts = current_alerts + forecast_alerts
    total_alerts = len(all_alerts)
    has_alerts = total_alerts > 0

    # Determine unique alert condition types triggered
    triggered_types = {a["alert_type"] for a in all_alerts}
    is_compound_risk = len(triggered_types) >= 2

    # Highest severity level observed across all alerts
    highest_severity: Optional[str] = None
    if has_alerts:
        severities = [a["severity"] for a in all_alerts]
        if "Warning" in severities:
            highest_severity = "Warning"
        elif "Watch" in severities:
            highest_severity = "Watch"
        else:
            highest_severity = "Advisory"

    # Human-readable summary
    if not has_alerts:
        summary_text = f"All weather parameters for {city} are currently within normal thresholds. No active alerts."
    else:
        types_str = ", ".join(sorted(triggered_types))
        compound_note = " (Compound Multi-Hazard Condition)" if is_compound_risk else ""
        summary_text = (
            f"{total_alerts} alert(s) detected for {city}{compound_note}: {types_str}. "
            f"Highest application severity: {highest_severity}."
        )

    return {
        "city": city,
        "data_source": data_source,
        "is_simulated": is_simulated,
        "has_alerts": has_alerts,
        "total_alerts": total_alerts,
        "is_compound_risk": is_compound_risk,
        "highest_severity": highest_severity,
        "triggered_types": sorted(list(triggered_types)),
        "current_alerts": current_alerts,
        "forecast_alerts": forecast_alerts,
        "all_alerts": all_alerts,
        "summary": summary_text,
        "thresholds_applied": {
            "temperature_c": thresholds.high_temp_c,
            "humidity_pct": thresholds.high_humidity_pct,
            "rain_probability_pct": thresholds.high_rain_prob_pct,
            "wind_speed_kmh": thresholds.high_wind_speed_kmh,
        },
        "disclaimer": OFFICIAL_WARNING_DISCLAIMER
    }
