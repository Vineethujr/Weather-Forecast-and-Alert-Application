"""
Unit tests for src/forecast_analysis.py.
Verifies statistical calculations, cumulative precipitation, wind gusts,
temperature trend classification (Warming, Cooling, Stable), chronological sorting,
empty DataFrame handling, and missing/null value resilience.
"""

import numpy as np
import pandas as pd
import pytest

from src.data_processing import process_weather_payload
from src.forecast_analysis import (
    calculate_forecast_statistics,
    determine_temperature_trend,
    generate_forecast_summary,
    identify_peak_intervals,
)
from src.weather_api import get_weather_data


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def sample_forecast_df() -> pd.DataFrame:
    """Standard 4-interval test DataFrame with realistic parameters."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=4, freq="3h"),
        "temperature_c": [22.0, 26.0, 28.5, 24.0],
        "humidity_pct": [75.0, 65.0, 60.0, 70.0],
        "rain_probability_pct": [10.0, 20.0, 40.0, 15.0],
        "precipitation_mm": [0.0, 0.5, 3.2, 0.1],
        "wind_speed_kmh": [12.0, 18.0, 22.5, 15.0],
        "weather_code": [0, 1, 61, 2],
        "weather_condition": ["Clear Sky", "Mainly Clear", "Slight Rain", "Partly Cloudy"]
    })


# ==============================================================================
# Statistical Calculations Tests
# ==============================================================================

def test_calculate_forecast_statistics(sample_forecast_df):
    """Verify min, max, mean, and cumulative sums are accurate."""
    stats = calculate_forecast_statistics(sample_forecast_df)

    # Temperature
    assert stats["temperature"]["min"] == 22.0
    assert stats["temperature"]["max"] == 28.5
    assert stats["temperature"]["mean"] == round((22.0 + 26.0 + 28.5 + 24.0) / 4, 2)

    # Humidity
    assert stats["humidity"]["min"] == 60.0
    assert stats["humidity"]["max"] == 75.0
    assert stats["humidity"]["mean"] == 67.5

    # Wind
    assert stats["wind_speed"]["min"] == 12.0
    assert stats["wind_speed"]["max"] == 22.5
    assert stats["wind_speed"]["max_gust"] == 22.5

    # Precipitation
    assert stats["precipitation"]["max_probability"] == 40.0
    assert stats["precipitation"]["cumulative_amount_mm"] == round(0.0 + 0.5 + 3.2 + 0.1, 2)


def test_calculate_forecast_statistics_wind_gust():
    """Verify explicit wind_gust_kmh column is respected when present."""
    df = pd.DataFrame({
        "wind_speed_kmh": [20.0, 30.0],
        "wind_gust_kmh": [45.0, 58.0]
    })
    stats = calculate_forecast_statistics(df)
    assert stats["wind_speed"]["max"] == 30.0
    assert stats["wind_speed"]["max_gust"] == 58.0


def test_calculate_forecast_statistics_empty_df():
    """Verify empty DataFrame returns None for all statistics without crashing."""
    stats = calculate_forecast_statistics(pd.DataFrame())
    assert stats["total_intervals"] == 0
    assert stats["temperature"]["min"] is None
    assert stats["temperature"]["max"] is None
    assert stats["temperature"]["mean"] is None
    assert stats["precipitation"]["cumulative_amount_mm"] is None


def test_calculate_forecast_statistics_with_nulls():
    """Verify NaN values are skipped and genuine zeros are preserved."""
    df = pd.DataFrame({
        "temperature_c": [20.0, np.nan, 30.0],
        "precipitation_mm": [0.0, np.nan, 5.0]
    })
    stats = calculate_forecast_statistics(df)
    assert stats["temperature"]["min"] == 20.0
    assert stats["temperature"]["max"] == 30.0
    assert stats["temperature"]["mean"] == 25.0
    assert stats["precipitation"]["cumulative_amount_mm"] == 5.0
    assert stats["data_quality"]["missing_temperature_count"] == 1


# ==============================================================================
# Temperature Trend Tests
# ==============================================================================

def test_temperature_trend_warming():
    """Verify Warming trend detection when delta exceeds tolerance."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=3, freq="3h"),
        "temperature_c": [20.0, 23.0, 26.0]  # delta = +6.0°C
    })
    result = determine_temperature_trend(df, tolerance_c=1.5)
    assert result["trend"] == "Warming"
    assert result["delta_c"] == 6.0
    assert result["start_temperature_c"] == 20.0
    assert result["end_temperature_c"] == 26.0


def test_temperature_trend_cooling():
    """Verify Cooling trend detection when delta is negative beyond tolerance."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=3, freq="3h"),
        "temperature_c": [30.0, 26.0, 24.0]  # delta = -6.0°C
    })
    result = determine_temperature_trend(df, tolerance_c=1.5)
    assert result["trend"] == "Cooling"
    assert result["delta_c"] == -6.0


def test_temperature_trend_stable():
    """Verify Stable trend when delta is within tolerance."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=3, freq="3h"),
        "temperature_c": [24.0, 24.8, 24.5]  # delta = +0.5°C
    })
    result = determine_temperature_trend(df, tolerance_c=1.5)
    assert result["trend"] == "Stable"
    assert result["delta_c"] == 0.5


def test_temperature_trend_unordered_timestamps():
    """Verify DataFrame is sorted chronologically before computing trend."""
    # Rows are placed in reverse chronological order
    df = pd.DataFrame({
        "timestamp": [
            pd.Timestamp("2026-11-24 18:00"),
            pd.Timestamp("2026-11-24 12:00"),
            pd.Timestamp("2026-11-24 06:00")
        ],
        "temperature_c": [28.0, 25.0, 20.0]  # Chronologically: 20 -> 25 -> 28 = Warming
    })
    result = determine_temperature_trend(df, tolerance_c=1.5)
    assert result["trend"] == "Warming"
    assert result["start_temperature_c"] == 20.0
    assert result["end_temperature_c"] == 28.0
    assert result["delta_c"] == 8.0


def test_temperature_trend_insufficient_data():
    """Verify Undetermined trend when fewer than 2 valid measurements exist."""
    df = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-11-24 06:00")],
        "temperature_c": [22.0]
    })
    result = determine_temperature_trend(df)
    assert result["trend"] == "Undetermined"


# ==============================================================================
# Peak Intervals Tests
# ==============================================================================

def test_identify_peak_intervals(sample_forecast_df):
    """Verify identification of peak weather intervals."""
    peaks = identify_peak_intervals(sample_forecast_df)
    assert peaks["peak_temperature"]["value"] == 28.5
    assert peaks["lowest_temperature"]["value"] == 22.0
    assert peaks["peak_rain_probability"]["value"] == 40.0
    assert peaks["peak_wind_speed"]["value"] == 22.5


def test_identify_peak_intervals_empty():
    """Verify empty DataFrame returns None peak fields without errors."""
    peaks = identify_peak_intervals(pd.DataFrame())
    assert peaks["peak_temperature"] is None
    assert peaks["lowest_temperature"] is None


# ==============================================================================
# End-to-End Master Forecast Summary Tests
# ==============================================================================

def test_generate_forecast_summary_simulated_scenario():
    """Verify end-to-end integration from simulation data through forecast analysis."""
    raw_payload = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
    processed_bundle = process_weather_payload(raw_payload)

    summary = generate_forecast_summary(
        df=processed_bundle["forecast_df"],
        metadata=processed_bundle
    )

    assert summary["data_source"] == "SIMULATED"
    assert summary["is_simulated"] is True
    assert summary["city"] == "Delhi"
    assert "Delhi" in summary["overview"]
    assert summary["statistics"]["temperature"]["max"] > 40.0
    assert summary["temperature_trend"]["trend"] in ["Warming", "Cooling", "Stable"]
    assert summary["peak_intervals"]["peak_temperature"] is not None


def test_generate_forecast_summary_empty_df():
    """Verify master summary handles an empty DataFrame cleanly."""
    summary = generate_forecast_summary(pd.DataFrame(), metadata={"city": "EmptyCity"})
    assert summary["city"] == "EmptyCity"
    assert "No forecast intervals available" in summary["overview"]
    assert summary["statistics"]["total_intervals"] == 0
