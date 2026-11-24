"""
Unit tests for src/weather_api.py.
Verifies geocoding, forecast fetching, error handling, timeouts,
WMO code translation, simulation loading, and response normalization.
All network calls are strictly mocked with unittest.mock to ensure offline reliability.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.weather_api import (
    APIConnectionError,
    APIResponseError,
    CityNotFoundError,
    NetworkTimeoutError,
    fetch_open_meteo_forecast,
    geocode_city,
    get_weather_data,
    load_simulation_data,
    normalize_live_response,
    translate_wmo_code,
)


# ==============================================================================
# Geocoding Tests (Mocked)
# ==============================================================================

def test_geocode_city_success():
    """Verify successful geocoding returns parsed latitude, longitude, and country."""
    mock_payload = {
        "results": [
            {
                "name": "Mangaluru",
                "latitude": 12.9141,
                "longitude": 74.856,
                "country": "India",
                "country_code": "IN",
                "timezone": "Asia/Kolkata"
            }
        ]
    }
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload
        mock_get.return_value = mock_response

        geo = geocode_city("Mangaluru")

        assert geo["city"] == "Mangaluru"
        assert geo["country"] == "India"
        assert geo["latitude"] == 12.9141
        assert geo["longitude"] == 74.856
        assert geo["timezone"] == "Asia/Kolkata"


def test_geocode_city_empty_input():
    """Verify empty or whitespace-only city names raise ValueError."""
    with pytest.raises(ValueError, match="City name cannot be empty"):
        geocode_city("   ")


def test_geocode_city_not_found():
    """Verify that an unknown city raises CityNotFoundError."""
    mock_payload = {"results": []}
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload
        mock_get.return_value = mock_response

        with pytest.raises(CityNotFoundError, match="was not found"):
            geocode_city("NonExistentCityXYZ123")


def test_geocode_city_timeout():
    """Verify network timeout raises NetworkTimeoutError."""
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Request timed out")):
        with pytest.raises(NetworkTimeoutError, match="timed out"):
            geocode_city("Tokyo")


def test_geocode_city_connection_error():
    """Verify DNS / socket failure raises APIConnectionError."""
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Network unreachable")):
        with pytest.raises(APIConnectionError, match="Failed to connect"):
            geocode_city("London")


def test_geocode_city_http_500():
    """Verify HTTP server error raises APIResponseError."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        with pytest.raises(APIResponseError, match="returned HTTP error"):
            geocode_city("Paris")


# ==============================================================================
# Weather Forecast Fetching Tests (Mocked)
# ==============================================================================

def test_fetch_forecast_success():
    """Verify fetching forecast returns raw API payload."""
    raw_sample = {
        "current": {
            "time": "2026-11-24T12:00",
            "temperature_2m": 29.5,
            "relative_humidity_2m": 65.0,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.0
        },
        "hourly": {
            "time": ["2026-11-24T12:00", "2026-11-24T13:00"],
            "temperature_2m": [29.5, 30.1],
            "relative_humidity_2m": [65.0, 63.0],
            "precipitation_probability": [10.0, 15.0],
            "precipitation": [0.0, 0.0],
            "weather_code": [1, 2],
            "wind_speed_10m": [12.0, 13.5]
        }
    }
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = raw_sample
        mock_get.return_value = mock_response

        data = fetch_open_meteo_forecast(12.91, 74.85)
        assert "current" in data
        assert "hourly" in data
        assert data["current"]["temperature_2m"] == 29.5


def test_fetch_forecast_timeout():
    """Verify forecast timeout raises NetworkTimeoutError."""
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
        with pytest.raises(NetworkTimeoutError):
            fetch_open_meteo_forecast(0.0, 0.0)


# ==============================================================================
# Normalization Tests
# ==============================================================================

def test_normalize_live_response():
    """Verify normalization preserves labels, units, and nested structures."""
    raw_sample = {
        "timezone": "Asia/Kolkata",
        "current": {
            "time": "2026-11-24T14:00",
            "temperature_2m": 31.0,
            "relative_humidity_2m": 70.0,
            "precipitation": 0.5,
            "weather_code": 61,
            "wind_speed_10m": 18.0
        },
        "hourly": {
            "time": ["2026-11-24T14:00", "2026-11-24T15:00"],
            "temperature_2m": [31.0, 30.5],
            "relative_humidity_2m": [70.0, 72.0],
            "precipitation_probability": [60.0, 65.0],
            "precipitation": [0.5, 1.2],
            "weather_code": [61, 63],
            "wind_speed_10m": [18.0, 19.5]
        }
    }
    geo_info = {
        "city": "Mangaluru",
        "country": "India",
        "latitude": 12.9141,
        "longitude": 74.856,
        "timezone": "Asia/Kolkata"
    }

    norm = normalize_live_response(raw_sample, geo_info)

    assert norm["data_source"] == "LIVE"
    assert norm["is_simulated"] is False
    assert norm["city"] == "Mangaluru"
    assert norm["country"] == "India"
    assert norm["current"]["temperature"] == 31.0
    assert norm["current"]["weather_condition"] == "Slight Rain"
    assert len(norm["forecast"]) == 2
    assert norm["forecast"][0]["precipitation_probability"] == 60.0


# ==============================================================================
# Simulation Loader Tests
# ==============================================================================

def test_load_simulation_normal_weather():
    """Verify loading normal_weather simulation scenario."""
    sim = load_simulation_data("normal_weather")
    assert sim["data_source"] == "SIMULATED"
    assert sim["is_simulated"] is True
    assert sim["scenario_id"] == "normal_weather"
    assert sim["city"] == "Mangaluru"
    assert len(sim["forecast"]) == 8


def test_load_simulation_compound_risks():
    """Verify compound_risks simulation scenario loads with stress-test attributes."""
    sim = load_simulation_data("compound_risks")
    assert sim["data_source"] == "SIMULATED"
    assert sim["current"]["temperature"] > 40.0
    assert sim["current"]["wind_speed"] > 50.0
    assert sim["current"]["humidity"] > 85.0


def test_load_simulation_invalid_scenario():
    """Verify invalid scenario raises ValueError with listed alternatives."""
    with pytest.raises(ValueError, match="Scenario 'non_existent_scenario' not found"):
        load_simulation_data("non_existent_scenario")


# ==============================================================================
# WMO Code Translation Tests
# ==============================================================================

def test_translate_wmo_code():
    """Verify WMO weather codes are translated accurately."""
    assert translate_wmo_code(0) == "Clear Sky"
    assert translate_wmo_code(65) == "Heavy Continuous Rain"
    assert translate_wmo_code(95) == "Thunderstorm"
    assert translate_wmo_code(None) == "Unknown Condition"
    assert translate_wmo_code(999) == "Weather Code 999"


# ==============================================================================
# Unified get_weather_data Tests
# ==============================================================================

def test_get_weather_data_simulation_mode():
    """Verify get_weather_data with use_simulation=True does not touch requests."""
    with patch("requests.get") as mock_get:
        result = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
        mock_get.assert_not_called()
        assert result["data_source"] == "SIMULATED"
        assert result["current"]["temperature"] > 40.0


def test_get_weather_data_live_mode():
    """Verify get_weather_data with use_simulation=False calls geocoding and forecast."""
    geo_mock = {
        "results": [{"name": "Delhi", "latitude": 28.61, "longitude": 77.2, "country": "India"}]
    }
    forecast_mock = {
        "current": {"temperature_2m": 35.0, "relative_humidity_2m": 40.0, "wind_speed_10m": 15.0},
        "hourly": {"time": [], "temperature_2m": [], "relative_humidity_2m": [], "precipitation_probability": [], "wind_speed_10m": []}
    }
    with patch("requests.get") as mock_get:
        resp_geo = MagicMock()
        resp_geo.status_code = 200
        resp_geo.json.return_value = geo_mock

        resp_fc = MagicMock()
        resp_fc.status_code = 200
        resp_fc.json.return_value = forecast_mock

        mock_get.side_effect = [resp_geo, resp_fc]

        result = get_weather_data(city_name="Delhi", use_simulation=False)
        assert result["data_source"] == "LIVE"
        assert result["city"] == "Delhi"
        assert result["current"]["temperature"] == 35.0
