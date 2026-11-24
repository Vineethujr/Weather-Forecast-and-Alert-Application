"""
Unit tests for src/weather_service.py.
Verifies end-to-end orchestration, mocked live workflow, offline simulation workflow,
missing measurement tolerance, chart generation, report persistence, and data provenance.
"""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.weather_api import CityNotFoundError
from src.weather_service import execute_weather_workflow


# ==============================================================================
# Simulation Workflow Tests
# ==============================================================================

def test_execute_weather_workflow_simulation(tmp_path):
    """Verify complete simulation workflow with charts and reports."""
    out_dir = tmp_path / "outputs"
    rep_dir = tmp_path / "reports"

    results = execute_weather_workflow(
        use_simulation=True,
        scenario_id="normal_weather",
        output_dir=out_dir,
        reports_dir=rep_dir
    )

    assert results["city"] == "Mangaluru"
    assert results["data_source"] == "SIMULATED"
    assert results["is_simulated"] is True
    assert isinstance(results["current"], dict)
    assert isinstance(results["forecast_df"], pd.DataFrame)
    assert len(results["forecast_df"]) == 8

    # Statistical summary
    assert "statistics" in results["forecast_summary"]
    assert results["forecast_summary"]["temperature_trend"]["trend"] in ["Warming", "Cooling", "Stable"]

    # Alerts
    assert "has_alerts" in results["alert_report"]
    assert results["alert_report"]["has_alerts"] is False

    # Charts
    assert "dashboard" in results["charts"]
    assert results["charts"]["dashboard"].exists()

    # Reports
    assert "csv_report" in results["reports"]
    assert results["reports"]["csv_report"].exists()
    assert results["reports"]["json_report"].exists()


def test_execute_weather_workflow_compound_risk(tmp_path):
    """Verify compound multi-hazard simulation triggers alerts across all 4 metrics."""
    results = execute_weather_workflow(
        use_simulation=True,
        scenario_id="compound_risks",
        output_dir=tmp_path / "outputs",
        reports_dir=tmp_path / "reports"
    )

    assert results["alert_report"]["has_alerts"] is True
    assert results["alert_report"]["is_compound_risk"] is True
    assert len(results["alert_report"]["triggered_types"]) == 4


# ==============================================================================
# Live Workflow (Mocked) Tests
# ==============================================================================

def test_execute_weather_workflow_live_mocked(tmp_path):
    """Verify live workflow with mocked geocoding and forecast HTTP requests."""
    geo_mock = {
        "results": [
            {
                "name": "London",
                "latitude": 51.5074,
                "longitude": -0.1278,
                "country": "United Kingdom",
                "timezone": "Europe/London"
            }
        ]
    }
    forecast_mock = {
        "timezone": "Europe/London",
        "current": {
            "time": "2026-11-24T12:00",
            "temperature_2m": 16.5,
            "relative_humidity_2m": 72.0,
            "precipitation": 0.0,
            "weather_code": 2,
            "wind_speed_10m": 18.0
        },
        "hourly": {
            "time": ["2026-11-24T12:00", "2026-11-24T15:00"],
            "temperature_2m": [16.5, 17.0],
            "relative_humidity_2m": [72.0, 70.0],
            "precipitation_probability": [20.0, 25.0],
            "precipitation": [0.0, 0.0],
            "weather_code": [2, 3],
            "wind_speed_10m": [18.0, 19.5]
        }
    }

    with patch("requests.get") as mock_get:
        resp_geo = MagicMock()
        resp_geo.status_code = 200
        resp_geo.json.return_value = geo_mock

        resp_fc = MagicMock()
        resp_fc.status_code = 200
        resp_fc.json.return_value = forecast_mock

        mock_get.side_effect = [resp_geo, resp_fc]

        results = execute_weather_workflow(
            city_name="London",
            use_simulation=False,
            output_dir=tmp_path / "outputs",
            reports_dir=tmp_path / "reports"
        )

        assert results["city"] == "London"
        assert results["country"] == "United Kingdom"
        assert results["data_source"] == "LIVE"
        assert results["is_simulated"] is False
        assert results["current"]["temperature_c"] == 16.5
        assert len(results["forecast_df"]) == 2


def test_execute_weather_workflow_city_not_found():
    """Verify CityNotFoundError is propagated accurately."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        with pytest.raises(CityNotFoundError):
            execute_weather_workflow(city_name="UnknownGhostCity999", use_simulation=False)
