"""
Unit tests for src/visualization.py.
Verifies chart rendering for temperature, humidity, precipitation, wind,
and multi-panel dashboards. Confirms file existence, non-zero sizes,
empty DataFrame handling, and figure cleanup to avoid memory leaks.
Uses pytest tmp_path to prevent polluting production directories.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src.data_processing import process_weather_payload
from src.visualization import (
    generate_all_forecast_charts,
    plot_combined_dashboard,
    plot_humidity_forecast,
    plot_precipitation_forecast,
    plot_temperature_forecast,
    plot_wind_forecast,
)
from src.weather_api import get_weather_data


@pytest.fixture
def sample_forecast_df() -> pd.DataFrame:
    """Fixture providing a standard 4-interval forecast DataFrame."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=4, freq="3h"),
        "temperature_c": [24.0, 29.5, 42.0, 38.0],
        "humidity_pct": [60.0, 75.0, 88.0, 92.0],
        "rain_probability_pct": [10.0, 30.0, 85.0, 90.0],
        "precipitation_mm": [0.0, 1.5, 25.0, 18.0],
        "wind_speed_kmh": [15.0, 32.0, 56.0, 48.0],
        "wind_gust_kmh": [22.0, 45.0, 72.0, 60.0],
        "weather_code": [0, 1, 65, 65],
        "weather_condition": ["Clear", "Partly Cloudy", "Heavy Rain", "Heavy Rain"]
    })


# ==============================================================================
# Individual Chart Tests
# ==============================================================================

def test_plot_temperature_forecast(tmp_path, sample_forecast_df):
    """Verify temperature chart is created as a valid, non-empty PNG file."""
    chart_path = plot_temperature_forecast(
        sample_forecast_df,
        city="Mangaluru",
        is_simulated=True,
        threshold_c=40.0,
        output_dir=tmp_path
    )
    assert chart_path.exists()
    assert chart_path.suffix == ".png"
    assert chart_path.stat().st_size > 1000  # Non-empty image file
    # Verify figure was closed
    assert len(plt.get_fignums()) == 0


def test_plot_humidity_forecast(tmp_path, sample_forecast_df):
    """Verify humidity chart generation and threshold line handling."""
    chart_path = plot_humidity_forecast(
        sample_forecast_df,
        city="Mumbai",
        is_simulated=False,
        threshold_pct=85.0,
        output_dir=tmp_path
    )
    assert chart_path.exists()
    assert chart_path.stat().st_size > 1000
    assert len(plt.get_fignums()) == 0


def test_plot_precipitation_forecast(tmp_path, sample_forecast_df):
    """Verify precipitation probability bar chart generation."""
    chart_path = plot_precipitation_forecast(
        sample_forecast_df,
        city="Kochi",
        is_simulated=True,
        threshold_pct=70.0,
        output_dir=tmp_path
    )
    assert chart_path.exists()
    assert chart_path.stat().st_size > 1000
    assert len(plt.get_fignums()) == 0


def test_plot_wind_forecast(tmp_path, sample_forecast_df):
    """Verify wind speed and gusts chart generation."""
    chart_path = plot_wind_forecast(
        sample_forecast_df,
        city="Chennai Coast",
        is_simulated=True,
        threshold_kmh=50.0,
        output_dir=tmp_path
    )
    assert chart_path.exists()
    assert chart_path.stat().st_size > 1000
    assert len(plt.get_fignums()) == 0


def test_plot_combined_dashboard(tmp_path, sample_forecast_df):
    """Verify multi-panel combined dashboard chart generation."""
    chart_path = plot_combined_dashboard(
        sample_forecast_df,
        city="Mangaluru",
        is_simulated=False,
        output_dir=tmp_path
    )
    assert chart_path.exists()
    assert chart_path.stat().st_size > 5000  # Multi-panel dashboard is larger
    assert len(plt.get_fignums()) == 0


# ==============================================================================
# Edge Cases: Empty Data & Missing Columns
# ==============================================================================

def test_visualization_empty_dataframe(tmp_path):
    """Verify plotting functions gracefully handle empty DataFrames without crashing."""
    empty_df = pd.DataFrame()
    
    t_path = plot_temperature_forecast(empty_df, city="EmptyCity", output_dir=tmp_path)
    assert t_path.exists()
    assert t_path.stat().st_size > 500

    dash_path = plot_combined_dashboard(empty_df, city="EmptyCity", output_dir=tmp_path)
    assert dash_path.exists()
    assert dash_path.stat().st_size > 500
    assert len(plt.get_fignums()) == 0


def test_visualization_missing_measurements(tmp_path):
    """Verify NaN measurements in series are plotted without error."""
    df_with_nans = pd.DataFrame({
        "timestamp": pd.date_range("2026-11-24 06:00", periods=3, freq="3h"),
        "temperature_c": [25.0, None, 30.0],
        "humidity_pct": [None, 80.0, None],
        "rain_probability_pct": [10.0, None, 50.0],
        "wind_speed_kmh": [None, None, 20.0]
    })
    chart_path = plot_temperature_forecast(df_with_nans, city="NaNTest", output_dir=tmp_path)
    assert chart_path.exists()
    assert len(plt.get_fignums()) == 0


def test_custom_output_dir_creation(tmp_path):
    """Verify nested non-existent directory is automatically created."""
    nested_dir = tmp_path / "deeply" / "nested" / "chart_dir"
    assert not nested_dir.exists()
    
    chart_path = plot_temperature_forecast(None, city="NestedTest", output_dir=nested_dir)
    assert nested_dir.exists()
    assert chart_path.exists()


# ==============================================================================
# Master Batch Generation & Memory Leak Checks
# ==============================================================================

def test_generate_all_forecast_charts(tmp_path):
    """Verify batch generator produces all 5 charts for a simulation scenario."""
    raw = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
    bundle = process_weather_payload(raw)

    results = generate_all_forecast_charts(
        df=bundle["forecast_df"],
        metadata=bundle,
        output_dir=tmp_path
    )

    expected_keys = {"temperature", "humidity", "precipitation", "wind", "dashboard"}
    assert set(results.keys()) == expected_keys

    for key, path in results.items():
        assert path.exists(), f"Chart {key} was not generated"
        assert path.stat().st_size > 1000

    # Verify no open figures remain in memory
    assert len(plt.get_fignums()) == 0


def test_repeated_chart_generation_no_memory_leak(tmp_path, sample_forecast_df):
    """Verify that repeatedly generating 10 charts does not leak open Matplotlib figures."""
    for i in range(10):
        plot_temperature_forecast(
            sample_forecast_df,
            city="LeakTest",
            output_dir=tmp_path,
            filename=f"leak_test_{i}.png"
        )
    assert len(plt.get_fignums()) == 0
