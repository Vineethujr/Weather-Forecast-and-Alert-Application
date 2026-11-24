"""
Unit tests for src/data_processing.py.
Tests DataFrame normalization, timestamp parsing, missing value handling,
range validation, malformed input rejection, and schema parity between LIVE and SIMULATED.
"""

from datetime import datetime
import numpy as np
import pandas as pd
import pytest

from src.data_processing import (
    DataProcessingError,
    FORECAST_COLUMNS,
    parse_iso_timestamp,
    process_current_weather,
    process_forecast_dataframe,
    process_weather_payload,
    validate_measurement,
)
from src.weather_api import get_weather_data


# ==============================================================================
# Timestamp Parsing Tests
# ==============================================================================

def test_parse_iso_timestamp_with_timezone():
    """Verify ISO 8601 timestamps with timezone offsets parse accurately."""
    ts_str = "2026-11-24T14:00:00+05:30"
    parsed = parse_iso_timestamp(ts_str)
    assert parsed is not None
    assert isinstance(parsed, pd.Timestamp)
    assert parsed.hour == 14
    assert parsed.minute == 0


def test_parse_iso_timestamp_utc():
    """Verify UTC ISO timestamp parsing."""
    ts_str = "2026-11-24T08:30:00Z"
    parsed = parse_iso_timestamp(ts_str)
    assert parsed is not None
    assert parsed.year == 2026


def test_parse_iso_timestamp_none_or_invalid():
    """Verify None or invalid timestamps return None gracefully."""
    assert parse_iso_timestamp(None) is None
    assert parse_iso_timestamp("invalid-date-string") is None


# ==============================================================================
# Measurement Range Validation Tests
# ==============================================================================

def test_validate_measurement_valid_range():
    """Verify values within range are converted to float."""
    warnings = []
    val = validate_measurement(25.4, -60.0, 60.0, "temp", warnings)
    assert val == 25.4
    assert len(warnings) == 0


def test_validate_measurement_preserves_none():
    """Verify missing/None values stay None and are NOT coerced to zero."""
    warnings = []
    val = validate_measurement(None, 0.0, 100.0, "humidity", warnings)
    assert val is None
    assert len(warnings) == 0


def test_validate_measurement_out_of_bounds():
    """Verify out-of-bounds measurements are logged and return None."""
    warnings = []
    # Humidity above 100%
    val = validate_measurement(115.0, 0.0, 100.0, "humidity", warnings)
    assert val is None
    assert len(warnings) == 1
    assert "out of physically reasonable bounds" in warnings[0]

    # Negative wind speed
    val_wind = validate_measurement(-10.0, 0.0, 400.0, "wind", warnings)
    assert val_wind is None
    assert len(warnings) == 2


def test_validate_measurement_non_numeric():
    """Verify unparseable string returns None with warning."""
    warnings = []
    val = validate_measurement("corrupt_value", 0.0, 100.0, "rain", warnings)
    assert val is None
    assert len(warnings) == 1
    assert "Invalid non-numeric value" in warnings[0]


# ==============================================================================
# Current Weather Processing Tests
# ==============================================================================

def test_process_current_weather_valid():
    """Verify current weather normalization with full metadata."""
    raw_current = {
        "timestamp": "2026-11-24T12:00:00+05:30",
        "temperature": 28.5,
        "humidity": 65.0,
        "wind_speed": 14.0,
        "precipitation_probability": 20.0,
        "precipitation_amount": 0.0,
        "weather_code": 1,
        "weather_condition": "Mainly Clear"
    }
    metadata = {
        "data_source": "SIMULATED",
        "is_simulated": True,
        "city": "Mangaluru",
        "country": "India"
    }

    processed = process_current_weather(raw_current, metadata)
    assert processed["data_source"] == "SIMULATED"
    assert processed["is_simulated"] is True
    assert processed["city"] == "Mangaluru"
    assert processed["temperature_c"] == 28.5
    assert processed["humidity_pct"] == 65.0
    assert processed["weather_condition"] == "Mainly Clear"


def test_process_current_weather_missing_fields():
    """Verify missing fields in current weather remain None, not 0.0."""
    raw_current = {
        "timestamp": "2026-11-24T12:00:00+05:30",
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "precipitation_probability": None,
        "precipitation_amount": None,
        "weather_code": None,
        "weather_condition": "Unknown Condition"
    }
    processed = process_current_weather(raw_current)
    assert processed["temperature_c"] is None
    assert processed["humidity_pct"] is None
    assert processed["wind_speed_kmh"] is None
    assert processed["rain_probability_pct"] is None


def test_process_current_weather_malformed_raises_error():
    """Verify non-dictionary current observation raises DataProcessingError."""
    with pytest.raises(DataProcessingError, match="Current weather data is missing"):
        process_current_weather(None)


# ==============================================================================
# Forecast DataFrame Normalization Tests
# ==============================================================================

def test_process_forecast_dataframe_valid():
    """Verify forecast intervals convert to structured DataFrame with typed columns."""
    intervals = [
        {
            "timestamp": "2026-11-24T06:00:00+05:30",
            "temperature": 22.0,
            "humidity": 75.0,
            "precipitation_probability": 10.0,
            "precipitation_amount": 0.0,
            "wind_speed": 12.0,
            "weather_code": 0,
            "weather_condition": "Clear Sky"
        },
        {
            "timestamp": "2026-11-24T09:00:00+05:30",
            "temperature": 26.5,
            "humidity": 68.0,
            "precipitation_probability": 15.0,
            "precipitation_amount": 0.0,
            "wind_speed": 14.5,
            "weather_code": 1,
            "weather_condition": "Mainly Clear"
        }
    ]
    df = process_forecast_dataframe(intervals)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == FORECAST_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert df["temperature_c"].iloc[0] == 22.0
    assert df["humidity_pct"].iloc[1] == 68.0


def test_process_forecast_dataframe_empty():
    """Verify empty forecast list returns empty DataFrame with expected columns."""
    df = process_forecast_dataframe([])
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert list(df.columns) == FORECAST_COLUMNS


def test_process_forecast_dataframe_with_nulls():
    """Verify null measurements in forecast are preserved as np.nan."""
    intervals = [
        {
            "timestamp": "2026-11-24T12:00:00+05:30",
            "temperature": None,
            "humidity": None,
            "precipitation_probability": None,
            "precipitation_amount": None,
            "wind_speed": None,
            "weather_code": None,
            "weather_condition": "Unknown"
        }
    ]
    df = process_forecast_dataframe(intervals)
    assert len(df) == 1
    assert np.isnan(df["temperature_c"].iloc[0])
    assert np.isnan(df["humidity_pct"].iloc[0])
    assert np.isnan(df["wind_speed_kmh"].iloc[0])


# ==============================================================================
# End-to-End Payload Processing Pipeline Tests
# ==============================================================================

def test_process_weather_payload_simulation():
    """Verify end-to-end processing of a simulated weather payload."""
    sim_raw = get_weather_data(use_simulation=True, scenario_id="normal_weather")
    bundle = process_weather_payload(sim_raw)

    assert bundle["data_source"] == "SIMULATED"
    assert bundle["is_simulated"] is True
    assert bundle["city"] == "Mangaluru"
    assert isinstance(bundle["current"], dict)
    assert isinstance(bundle["forecast_df"], pd.DataFrame)
    assert len(bundle["forecast_df"]) == 8
    assert bundle["current"]["temperature_c"] == 27.5


def test_process_weather_payload_schema_parity():
    """Verify that LIVE and SIMULATED payloads yield identical dictionary keys and DataFrame columns."""
    sim_raw = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
    sim_bundle = process_weather_payload(sim_raw)

    # Synthetic mock of live payload
    live_raw = {
        "data_source": "LIVE",
        "is_simulated": False,
        "city": "London",
        "country": "United Kingdom",
        "coordinates": {"latitude": 51.5, "longitude": -0.12},
        "timezone": "Europe/London",
        "retrieved_at": "2026-11-24T14:00:00Z",
        "current": {
            "timestamp": "2026-11-24T14:00:00Z",
            "temperature": 15.0,
            "humidity": 60.0,
            "wind_speed": 18.0,
            "precipitation_probability": 25.0,
            "precipitation_amount": 0.2,
            "weather_code": 3,
            "weather_condition": "Overcast"
        },
        "forecast": [
            {
                "timestamp": "2026-11-24T15:00:00Z",
                "temperature": 14.5,
                "humidity": 62.0,
                "precipitation_probability": 30.0,
                "precipitation_amount": 0.4,
                "wind_speed": 19.0,
                "weather_code": 3,
                "weather_condition": "Overcast"
            }
        ]
    }
    live_bundle = process_weather_payload(live_raw)

    # Top-level keys parity
    assert set(sim_bundle.keys()) == set(live_bundle.keys())
    # Current keys parity
    assert set(sim_bundle["current"].keys()) == set(live_bundle["current"].keys())
    # Forecast columns parity
    assert list(sim_bundle["forecast_df"].columns) == list(live_bundle["forecast_df"].columns)


def test_process_weather_payload_malformed_raises_error():
    """Verify missing 'current' section raises DataProcessingError."""
    with pytest.raises(DataProcessingError, match="missing required 'current' observations"):
        process_weather_payload({"city": "Delhi"})

    with pytest.raises(DataProcessingError, match="must be a non-empty dictionary"):
        process_weather_payload(None)
