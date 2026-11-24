"""
Data Processing & DataFrame Normalization Module.
Parses, cleans, validates, and normalizes current observations and forecast intervals
into robust Python dictionaries and Pandas DataFrames.
Enforces physical range validation while strictly preserving missing values as missing.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ==============================================================================
# Physical Measurement Validation Ranges (Configurable)
# ==============================================================================

VALID_RANGE_TEMP_C: Tuple[float, float] = (-60.0, 60.0)         # Physical ambient extremes
VALID_RANGE_HUMIDITY: Tuple[float, float] = (0.0, 100.0)         # Relative humidity percentage
VALID_RANGE_RAIN_PROB: Tuple[float, float] = (0.0, 100.0)        # Precipitation probability percentage
VALID_RANGE_WIND_SPEED: Tuple[float, float] = (0.0, 400.0)       # Wind speed in km/h (up to category 5+)
VALID_RANGE_PRECIPITATION: Tuple[float, float] = (0.0, 1000.0)   # Rainfall depth in mm


# ==============================================================================
# Custom Exception
# ==============================================================================

class DataProcessingError(Exception):
    """Raised when weather payload is malformed or cannot be parsed."""
    pass


# ==============================================================================
# Helper Functions: Timestamp Parsing & Range Validation
# ==============================================================================

def parse_iso_timestamp(timestamp_str: Any) -> Optional[pd.Timestamp]:
    """
    Parses an ISO 8601 timestamp string into a pandas Timestamp object.
    Preserves timezone offsets if present.
    
    Args:
        timestamp_str: ISO string (e.g. '2026-11-24T14:00:00+05:30' or '2026-11-24T14:00').
        
    Returns:
        pd.Timestamp or None if unparseable or missing.
    """
    if timestamp_str is None or pd.isna(timestamp_str):
        return None
    try:
        return pd.to_datetime(timestamp_str)
    except Exception as exc:
        logger.warning(f"Could not parse timestamp '{timestamp_str}': {exc}")
        return None


def validate_measurement(
    value: Any,
    min_val: float,
    max_val: float,
    field_name: str,
    warnings_list: Optional[List[str]] = None
) -> Optional[float]:
    """
    Validates that a numeric measurement falls within physically reasonable bounds.
    Preserves missing values as None rather than coercing them to zero.
    
    Args:
        value: Numeric measurement or None.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        field_name: Human-friendly name for reporting warnings.
        warnings_list: Optional list to append out-of-bounds warning messages.
        
    Returns:
        float if valid, or None if missing or out-of-bounds.
    """
    if value is None or pd.isna(value):
        return None

    try:
        float_val = float(value)
    except (ValueError, TypeError):
        msg = f"Invalid non-numeric value for {field_name}: '{value}'"
        logger.warning(msg)
        if warnings_list is not None:
            warnings_list.append(msg)
        return None

    if float_val < min_val or float_val > max_val:
        msg = (
            f"Measurement out of physically reasonable bounds for {field_name}: "
            f"{float_val} (expected between {min_val} and {max_val})"
        )
        logger.warning(msg)
        if warnings_list is not None:
            warnings_list.append(msg)
        return None

    return float_val


# ==============================================================================
# Current Weather Observation Processing
# ==============================================================================

def process_current_weather(
    current_raw: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    warnings_list: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validates and normalizes current weather observations.
    
    Args:
        current_raw: Raw dictionary containing current weather observations.
        metadata: Top-level metadata (city, country, data_source, etc.).
        warnings_list: Optional accumulator for non-fatal validation warnings.
        
    Returns:
        Standardized dictionary containing validated measurements and source provenance.
    """
    if current_raw is None or not isinstance(current_raw, dict):
        raise DataProcessingError("Current weather data is missing or malformed.")

    if metadata is None:
        metadata = {}

    # Validate individual fields; missing values stay None
    temp = validate_measurement(
        current_raw.get("temperature"),
        VALID_RANGE_TEMP_C[0],
        VALID_RANGE_TEMP_C[1],
        "current temperature (°C)",
        warnings_list
    )
    humidity = validate_measurement(
        current_raw.get("humidity"),
        VALID_RANGE_HUMIDITY[0],
        VALID_RANGE_HUMIDITY[1],
        "current humidity (%)",
        warnings_list
    )
    wind_speed = validate_measurement(
        current_raw.get("wind_speed"),
        VALID_RANGE_WIND_SPEED[0],
        VALID_RANGE_WIND_SPEED[1],
        "current wind speed (km/h)",
        warnings_list
    )
    rain_prob = validate_measurement(
        current_raw.get("precipitation_probability"),
        VALID_RANGE_RAIN_PROB[0],
        VALID_RANGE_RAIN_PROB[1],
        "current precipitation probability (%)",
        warnings_list
    )
    precip_amt = validate_measurement(
        current_raw.get("precipitation_amount"),
        VALID_RANGE_PRECIPITATION[0],
        VALID_RANGE_PRECIPITATION[1],
        "current precipitation amount (mm)",
        warnings_list
    )

    weather_code = current_raw.get("weather_code")
    if weather_code is not None:
        try:
            weather_code = int(weather_code)
        except (ValueError, TypeError):
            weather_code = None

    parsed_time = parse_iso_timestamp(current_raw.get("timestamp"))

    return {
        "data_source": metadata.get("data_source", "UNKNOWN"),
        "is_simulated": bool(metadata.get("is_simulated", False)),
        "city": metadata.get("city", "Unknown City"),
        "country": metadata.get("country", "Unknown Country"),
        "timestamp": parsed_time,
        "temperature_c": temp,
        "humidity_pct": humidity,
        "wind_speed_kmh": wind_speed,
        "rain_probability_pct": rain_prob,
        "precipitation_mm": precip_amt,
        "weather_code": weather_code,
        "weather_condition": current_raw.get("weather_condition", "Unknown Condition"),
        "units": {
            "temperature": "°C",
            "humidity": "%",
            "wind_speed": "km/h",
            "precipitation": "mm",
            "rain_probability": "%"
        }
    }


# ==============================================================================
# Forecast Normalization to Pandas DataFrame
# ==============================================================================

FORECAST_COLUMNS = [
    "timestamp",
    "temperature_c",
    "humidity_pct",
    "rain_probability_pct",
    "precipitation_mm",
    "wind_speed_kmh",
    "weather_code",
    "weather_condition"
]


def process_forecast_dataframe(
    forecast_list: Optional[List[Dict[str, Any]]],
    warnings_list: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Transforms a list of forecast interval dictionaries into a standardized Pandas DataFrame.
    Validates numeric ranges, parses timestamps, and preserves null values as NaN.
    
    Args:
        forecast_list: List of forecast interval dictionaries.
        warnings_list: Optional accumulator for non-fatal validation warnings.
        
    Returns:
        pd.DataFrame indexed by parsed timestamp or default range index with standardized columns.
    """
    if forecast_list is None or not isinstance(forecast_list, list) or len(forecast_list) == 0:
        # Return empty DataFrame with standardized column schema
        empty_df = pd.DataFrame(columns=FORECAST_COLUMNS)
        empty_df["timestamp"] = pd.to_datetime(empty_df["timestamp"])
        return empty_df

    cleaned_rows: List[Dict[str, Any]] = []

    for idx, interval in enumerate(forecast_list):
        if not isinstance(interval, dict):
            msg = f"Skipping malformed forecast interval at index {idx} (expected dictionary)."
            logger.warning(msg)
            if warnings_list is not None:
                warnings_list.append(msg)
            continue

        parsed_ts = parse_iso_timestamp(interval.get("timestamp"))

        temp = validate_measurement(
            interval.get("temperature"),
            VALID_RANGE_TEMP_C[0],
            VALID_RANGE_TEMP_C[1],
            f"forecast[{idx}] temperature",
            warnings_list
        )
        hum = validate_measurement(
            interval.get("humidity"),
            VALID_RANGE_HUMIDITY[0],
            VALID_RANGE_HUMIDITY[1],
            f"forecast[{idx}] humidity",
            warnings_list
        )
        rain_prob = validate_measurement(
            interval.get("precipitation_probability"),
            VALID_RANGE_RAIN_PROB[0],
            VALID_RANGE_RAIN_PROB[1],
            f"forecast[{idx}] rain probability",
            warnings_list
        )
        precip = validate_measurement(
            interval.get("precipitation_amount"),
            VALID_RANGE_PRECIPITATION[0],
            VALID_RANGE_PRECIPITATION[1],
            f"forecast[{idx}] precipitation amount",
            warnings_list
        )
        wind = validate_measurement(
            interval.get("wind_speed"),
            VALID_RANGE_WIND_SPEED[0],
            VALID_RANGE_WIND_SPEED[1],
            f"forecast[{idx}] wind speed",
            warnings_list
        )

        w_code = interval.get("weather_code")
        if w_code is not None:
            try:
                w_code = int(w_code)
            except (ValueError, TypeError):
                w_code = None

        cleaned_rows.append({
            "timestamp": parsed_ts,
            "temperature_c": temp if temp is not None else np.nan,
            "humidity_pct": hum if hum is not None else np.nan,
            "rain_probability_pct": rain_prob if rain_prob is not None else np.nan,
            "precipitation_mm": precip if precip is not None else np.nan,
            "wind_speed_kmh": wind if wind is not None else np.nan,
            "weather_code": w_code,
            "weather_condition": interval.get("weather_condition", "Unknown")
        })

    if not cleaned_rows:
        empty_df = pd.DataFrame(columns=FORECAST_COLUMNS)
        empty_df["timestamp"] = pd.to_datetime(empty_df["timestamp"])
        return empty_df

    df = pd.DataFrame(cleaned_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


# ==============================================================================
# Master Weather Processing Pipeline
# ==============================================================================

def process_weather_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entry point for the data processing engine.
    Ingests output from src/weather_api.py, performs full validation, and normalizes
    current observations and forecast intervals into standardized structures.
    
    Args:
        payload: Weather data dictionary (LIVE or SIMULATED) from weather_api.py.
        
    Returns:
        Structured bundle containing:
        - metadata (city, country, data_source, is_simulated, coordinates, etc.)
        - current: Validated current weather dict
        - forecast_df: Standardized Pandas DataFrame of forecast intervals
        - warnings: List of any non-fatal validation warnings encountered
        
    Raises:
        DataProcessingError: If payload is missing, not a dictionary, or lacks required sections.
    """
    if payload is None or not isinstance(payload, dict):
        raise DataProcessingError("Payload must be a non-empty dictionary.")

    warnings_list: List[str] = []

    # Verify essential top-level sections
    if "current" not in payload:
        raise DataProcessingError("Payload missing required 'current' observations section.")

    data_source = payload.get("data_source", "UNKNOWN").upper()
    is_simulated = bool(payload.get("is_simulated", data_source == "SIMULATED"))
    city = payload.get("city", "Unknown City")
    country = payload.get("country", "Unknown Country")
    coordinates = payload.get("coordinates", {"latitude": 0.0, "longitude": 0.0})
    timezone_str = payload.get("timezone", "UTC")
    retrieved_at = parse_iso_timestamp(payload.get("retrieved_at", datetime.utcnow().isoformat()))

    metadata = {
        "data_source": data_source,
        "is_simulated": is_simulated,
        "city": city,
        "country": country,
        "coordinates": coordinates,
        "timezone": timezone_str,
        "retrieved_at": retrieved_at
    }

    # 1. Process current observations
    current_processed = process_current_weather(
        current_raw=payload.get("current"),
        metadata=metadata,
        warnings_list=warnings_list
    )

    # 2. Process forecast intervals into DataFrame
    raw_forecast = payload.get("forecast", [])
    forecast_df = process_forecast_dataframe(
        forecast_list=raw_forecast,
        warnings_list=warnings_list
    )

    return {
        "data_source": data_source,
        "is_simulated": is_simulated,
        "city": city,
        "country": country,
        "coordinates": coordinates,
        "timezone": timezone_str,
        "retrieved_at": retrieved_at,
        "units": payload.get("units", {
            "temperature": "°C",
            "humidity": "%",
            "wind_speed": "km/h",
            "precipitation": "mm",
            "rain_probability": "%"
        }),
        "current": current_processed,
        "forecast_df": forecast_df,
        "warnings": warnings_list
    }
