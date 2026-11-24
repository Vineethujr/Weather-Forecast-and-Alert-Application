"""
Weather Report Generation and Storage Module.
Provides robust serialization of current observations into persistent CSV logs
and exports complete hierarchical JSON audit reports (current conditions,
forecast intervals, statistical summaries, and rule-based alerts).
Enforces atomic file replacement, missing-value preservation, timezone consistency,
sanitized path generation, and non-official safety disclaimers.
"""

import csv
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default reports directory
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
DEFAULT_CSV_FILENAME = "weather_reports.csv"

# Mandatory CSV schema specification
CSV_MANDATORY_COLUMNS = [
    "city",
    "timestamp",
    "temperature",
    "humidity",
    "wind_speed",
    "rain_probability",
    "weather_condition",
    "alert_messages",
    "data_source",
]


class ReportGenerationError(Exception):
    """Raised when report generation, serialization, or file persistence fails."""
    pass


# ==============================================================================
# Helper & Serialization Utilities
# ==============================================================================

def _get_reports_dir(custom_dir: Optional[Path] = None) -> Path:
    """Ensures reports destination directory exists and returns resolved Path."""
    target_dir = custom_dir if custom_dir is not None else DEFAULT_REPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def sanitize_filename_part(name: str) -> str:
    """
    Sanitizes arbitrary strings into safe, path-traversal-free filename components.
    Removes slashes, colons, dots, and replaces spaces with underscores.
    """
    if not name or not str(name).strip():
        return "unnamed"
    clean = re.sub(r"[^\w\-]", "_", str(name).strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "unnamed"


def _json_serial_default(obj: Any) -> Any:
    """Custom JSON serializer handling Pandas Timestamps, DataFrames, and NumPy scalar types."""
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, pd.DataFrame):
        # Convert DataFrame to records, replacing NaN with None
        clean_df = obj.replace({np.nan: None})
        return clean_df.to_dict(orient="records")
    elif isinstance(obj, (set, tuple)):
        return list(obj)
    elif pd.isna(obj):
        return None
    raise TypeError(f"Object of type '{type(obj).__name__}' is not JSON serializable")


def _sanitize_dict_for_json(data: Any) -> Any:
    """Recursively converts NaN values to None and serializes Timestamps."""
    if isinstance(data, bool):
        return data
    elif isinstance(data, dict):
        return {k: _sanitize_dict_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_dict_for_json(item) for item in data]
    elif isinstance(data, (pd.Timestamp, datetime)):
        return data.isoformat()
    elif isinstance(data, (np.floating, float)):
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    elif isinstance(data, (np.integer, int)):
        return int(data)
    elif isinstance(data, pd.DataFrame):
        return data.replace({np.nan: None}).to_dict(orient="records")
    elif pd.isna(data):
        return None
    return data


# ==============================================================================
# 1. CSV Weather Observation History
# ==============================================================================

def append_weather_observation(
    current_data: Optional[Dict[str, Any]],
    alerts: Optional[List[Dict[str, Any]]] = None,
    csv_path: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Path:
    """
    Appends a single current weather observation to reports/weather_reports.csv.
    
    Guarantees:
    - Writes CSV header only if the target file does not exist or is empty.
    - Appends without overwriting historical rows.
    - Preserves missing values as empty strings (''), never replacing with 0.
    - Serializes timestamps in ISO 8601 format.
    - Distinguishes LIVE vs SIMULATED provenance.
    
    Args:
        current_data: Processed current weather dictionary.
        alerts: Optional list of triggered alert dictionaries for this observation.
        csv_path: Optional explicit path to destination CSV file.
        reports_dir: Optional directory if csv_path is not specified.
        metadata: Optional top-level metadata dictionary.
        
    Returns:
        Path to the updated CSV file.
        
    Raises:
        ReportGenerationError: If input data is malformed or writing fails.
    """
    if current_data is None or not isinstance(current_data, dict):
        raise ReportGenerationError("Current weather observation data must be a valid dictionary.")

    if metadata is None:
        metadata = {}

    target_csv = csv_path if csv_path is not None else _get_reports_dir(reports_dir) / DEFAULT_CSV_FILENAME

    # Extract fields with safe fallbacks and empty-string missing-value preservation
    city = current_data.get("city") or metadata.get("city", "Unknown City")
    data_source = current_data.get("data_source") or metadata.get("data_source", "UNKNOWN")

    # Timestamp serialization
    ts_val = current_data.get("timestamp")
    if isinstance(ts_val, (pd.Timestamp, datetime)):
        timestamp_str = ts_val.isoformat()
    elif ts_val is not None and not pd.isna(ts_val):
        timestamp_str = str(ts_val)
    else:
        timestamp_str = datetime.now(timezone.utc).isoformat()

    def _format_cell(val: Any) -> str:
        if val is None or pd.isna(val) or val == "":
            return ""
        try:
            float_val = float(val)
            # Check for NaN float
            if np.isnan(float_val):
                return ""
            return f"{float_val:.1f}" if not float_val.is_integer() else f"{int(float_val)}"
        except (ValueError, TypeError):
            return str(val)

    temp_str = _format_cell(current_data.get("temperature_c", current_data.get("temperature")))
    hum_str = _format_cell(current_data.get("humidity_pct", current_data.get("humidity")))
    wind_str = _format_cell(current_data.get("wind_speed_kmh", current_data.get("wind_speed")))
    rain_str = _format_cell(current_data.get("rain_probability_pct", current_data.get("precipitation_probability")))
    condition_str = str(current_data.get("weather_condition", ""))

    # Format concatenated alert messages
    alert_messages: List[str] = []
    if alerts and isinstance(alerts, list):
        for a in alerts:
            if isinstance(a, dict):
                msg = a.get("message") or a.get("alert_type")
                if msg:
                    alert_messages.append(str(msg))

    alerts_cell = " | ".join(alert_messages) if alert_messages else "None"

    row_data = {
        "city": city,
        "timestamp": timestamp_str,
        "temperature": temp_str,
        "humidity": hum_str,
        "wind_speed": wind_str,
        "rain_probability": rain_str,
        "weather_condition": condition_str,
        "alert_messages": alerts_cell,
        "data_source": data_source,
    }

    # Determine whether header should be written
    write_header = not target_csv.exists() or target_csv.stat().st_size == 0

    try:
        with open(target_csv, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_MANDATORY_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row_data)
    except Exception as exc:
        logger.error(f"Failed to append weather observation to CSV '{target_csv}': {exc}")
        raise ReportGenerationError(f"CSV file writing error: {exc}") from exc

    logger.info(f"Appended weather observation for {city} to {target_csv}")
    return target_csv


# ==============================================================================
# 2. JSON Weather Audit Report (Atomic Write)
# ==============================================================================

def generate_json_report(
    weather_bundle: Optional[Dict[str, Any]],
    forecast_summary: Optional[Dict[str, Any]] = None,
    alert_report: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Generates a comprehensive, hierarchical JSON audit report containing current weather,
    normalized forecast intervals, statistical analysis, and active alerts.
    
    Guarantees:
    - Atomic write: writes to a temporary file (.tmp) and atomically renames to target.
    - Full serialization of Pandas Timestamps, DataFrames, and NumPy floats/nulls.
    - Explicit LIVE vs SIMULATED labeling.
    - Inclusion of mandatory non-official alert disclaimers.
    
    Args:
        weather_bundle: Processed weather bundle from src/data_processing.py.
        forecast_summary: Statistical summary from src/forecast_analysis.py.
        alert_report: Alert evaluation report from src/alert_system.py.
        output_dir: Optional custom directory to store the report.
        filename: Optional explicit filename.
        
    Returns:
        Path to the saved JSON report.
        
    Raises:
        ReportGenerationError: If weather_bundle is invalid or file writing fails.
    """
    if weather_bundle is None or not isinstance(weather_bundle, dict):
        raise ReportGenerationError("weather_bundle must be a non-empty dictionary.")

    target_dir = _get_reports_dir(output_dir)

    city = weather_bundle.get("city", "Unknown City")
    data_source = weather_bundle.get("data_source", "UNKNOWN")
    is_simulated = bool(weather_bundle.get("is_simulated", False))
    now_utc = datetime.now(timezone.utc)

    # Generate sanitized descriptive filename if none provided
    if filename:
        final_filename = filename
    else:
        city_slug = sanitize_filename_part(city)
        time_slug = now_utc.strftime("%Y%m%d_%H%M%S")
        final_filename = f"{city_slug}_report_{time_slug}.json"

    final_path = target_dir / final_filename
    temp_path = target_dir / f"{final_filename}.tmp"

    # Assemble structured report payload
    report_payload: Dict[str, Any] = {
        "metadata": {
            "report_generated_at": now_utc.isoformat(),
            "generator": "Weather Forecast & Alert Application",
            "version": "1.0.0",
            "city": city,
            "country": weather_bundle.get("country", "Unknown"),
            "coordinates": weather_bundle.get("coordinates", {"latitude": 0.0, "longitude": 0.0}),
            "timezone": weather_bundle.get("timezone", "UTC"),
            "data_source": data_source,
            "is_simulated": is_simulated,
            "units": weather_bundle.get("units", {}),
            "disclaimer": (
                "These are informational, rule-based application reports and are not official meteorological warnings. "
                "Follow relevant government weather agencies and local authorities for safety instructions."
            )
        },
        "current_weather": weather_bundle.get("current", {}),
        "forecast_intervals": weather_bundle.get("forecast_df"),
        "forecast_analysis": forecast_summary or {},
        "alerts": alert_report or {
            "has_alerts": False,
            "total_alerts": 0,
            "all_alerts": [],
            "summary": "No alert evaluation provided."
        }
    }

    # Sanitize and serialize to JSON string
    try:
        clean_payload = _sanitize_dict_for_json(report_payload)
        json_content = json.dumps(clean_payload, default=_json_serial_default, indent=2)
    except Exception as exc:
        logger.error(f"JSON serialization error for {city}: {exc}")
        raise ReportGenerationError(f"Failed to serialize report payload to JSON: {exc}") from exc

    # Atomic write pattern: write to .tmp and replace
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(json_content)
        # Atomically replace temporary file with destination
        os.replace(temp_path, final_path)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        logger.error(f"File writing failure for '{final_path}': {exc}")
        raise ReportGenerationError(f"Failed to write JSON report to '{final_path}': {exc}") from exc

    logger.info(f"Generated atomic JSON report at {final_path}")
    return final_path


# ==============================================================================
# 3. Report Loader Utility
# ==============================================================================

def load_weather_report(json_path: Path) -> Dict[str, Any]:
    """
    Loads and parses a previously generated JSON weather report.
    
    Args:
        json_path: Path to the JSON report file.
        
    Returns:
        Parsed dictionary.
        
    Raises:
        FileNotFoundError: If the specified report does not exist.
        ReportGenerationError: If the file contains invalid JSON.
    """
    target = Path(json_path)
    if not target.exists():
        raise FileNotFoundError(f"Report file not found: {target}")

    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ReportGenerationError(f"Corrupted or invalid JSON in report '{target}': {exc}") from exc


# ==============================================================================
# 4. Master Report Orchestrator
# ==============================================================================

def generate_weather_report(
    weather_bundle: Dict[str, Any],
    forecast_summary: Optional[Dict[str, Any]] = None,
    alert_report: Optional[Dict[str, Any]] = None,
    reports_dir: Optional[Path] = None
) -> Dict[str, Path]:
    """
    Master coordinator that generates both the persistent CSV history row
    and the standalone atomic JSON audit report.
    
    Args:
        weather_bundle: Processed weather bundle from data_processing.py.
        forecast_summary: Statistical summary from forecast_analysis.py.
        alert_report: Alert evaluation report from alert_system.py.
        reports_dir: Optional custom destination directory.
        
    Returns:
        Dict containing paths to:
        - "csv_report": Path to updated weather_reports.csv
        - "json_report": Path to generated JSON report
    """
    if weather_bundle is None or not isinstance(weather_bundle, dict):
        raise ReportGenerationError("weather_bundle must be a valid dictionary.")

    out_dir = _get_reports_dir(reports_dir)

    # 1. Append current weather observation to CSV
    current_data = weather_bundle.get("current", {})
    active_alerts = (alert_report.get("current_alerts") if alert_report else None) or []
    csv_file = append_weather_observation(
        current_data=current_data,
        alerts=active_alerts,
        reports_dir=out_dir,
        metadata=weather_bundle
    )

    # 2. Generate atomic JSON report
    json_file = generate_json_report(
        weather_bundle=weather_bundle,
        forecast_summary=forecast_summary,
        alert_report=alert_report,
        output_dir=out_dir
    )

    return {
        "csv_report": csv_file,
        "json_report": json_file
    }
