"""
Weather API Integration Module.
Handles geocoding (city name to coordinates), network requests to Open-Meteo REST API,
error handling, timeout management, simulation loading, and unified data normalization.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Base API Endpoints (Open-Meteo Public API)
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT_SECONDS = 10


# ==============================================================================
# Custom Exceptions for Granular Error Handling
# ==============================================================================

class WeatherAPIException(Exception):
    """Base exception for all weather API and networking errors."""
    pass


class CityNotFoundError(WeatherAPIException):
    """Raised when a city name cannot be resolved to coordinates."""
    pass


class NetworkTimeoutError(WeatherAPIException):
    """Raised when an HTTP request times out."""
    pass


class APIConnectionError(WeatherAPIException):
    """Raised when network connectivity fails (DNS resolution, connection refused)."""
    pass


class APIResponseError(WeatherAPIException):
    """Raised when the API returns an unexpected HTTP error code or malformed JSON."""
    pass


# ==============================================================================
# WMO Weather Interpretation Code Translation
# ==============================================================================

WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    56: "Light Freezing Drizzle",
    57: "Dense Freezing Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Continuous Rain",
    66: "Light Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Slight Snow Fall",
    73: "Moderate Snow Fall",
    75: "Heavy Snow Fall",
    77: "Snow Grains",
    80: "Slight Rain Showers",
    81: "Moderate Rain Showers",
    82: "Violent Rain Showers",
    85: "Slight Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Slight Hail",
    99: "Thunderstorm with Heavy Hail",
}


def translate_wmo_code(code: Optional[int]) -> str:
    """
    Translates a World Meteorological Organization (WMO) weather interpretation code
    into a human-readable English condition description.
    
    Args:
        code: Integer WMO weather code (e.g., 0, 65, 95).
        
    Returns:
        Readable description string (e.g., "Heavy Continuous Rain").
    """
    if code is None:
        return "Unknown Condition"
    return WMO_WEATHER_CODES.get(int(code), f"Weather Code {code}")


# ==============================================================================
# Geocoding: City Name -> Geographic Coordinates
# ==============================================================================

def geocode_city(city_name: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Resolves a human-entered city name into latitude, longitude, and country
    using the Open-Meteo Geocoding API.
    
    Args:
        city_name: Name of the city (e.g., "Mangaluru", "London").
        timeout: Request timeout duration in seconds.
        
    Returns:
        Dict containing resolved city name, country, latitude, longitude, and timezone.
        
    Raises:
        ValueError: If city_name is empty or whitespace only.
        CityNotFoundError: If the geocoding service finds no matching city.
        NetworkTimeoutError: If the geocoding service times out.
        APIConnectionError: If network connection drops or DNS fails.
        APIResponseError: If server responds with HTTP 4xx/5xx or invalid payload.
    """
    if not city_name or not city_name.strip():
        raise ValueError("City name cannot be empty or blank.")
        
    cleaned_city = city_name.strip()
    params = {
        "name": cleaned_city,
        "count": 1,
        "language": "en",
        "format": "json"
    }
    
    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.Timeout as exc:
        logger.error(f"Geocoding request timed out for city: {cleaned_city}")
        raise NetworkTimeoutError(f"Connection timed out while searching for city '{cleaned_city}'.") from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error(f"Geocoding connection failed for city: {cleaned_city}")
        raise APIConnectionError(f"Failed to connect to geocoding service. Please check your network connection.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.error(f"Geocoding HTTP error {response.status_code} for city: {cleaned_city}")
        raise APIResponseError(f"Geocoding service returned HTTP error: {response.status_code}") from exc
    except json.JSONDecodeError as exc:
        logger.error(f"Geocoding JSON decode error for city: {cleaned_city}")
        raise APIResponseError("Geocoding service returned invalid, non-JSON response.") from exc

    results = payload.get("results")
    if not results or not isinstance(results, list) or len(results) == 0:
        raise CityNotFoundError(f"City '{cleaned_city}' was not found. Please verify the spelling.")

    first_result = results[0]
    return {
        "city": first_result.get("name", cleaned_city),
        "country": first_result.get("country", "Unknown"),
        "country_code": first_result.get("country_code", ""),
        "latitude": float(first_result["latitude"]),
        "longitude": float(first_result["longitude"]),
        "timezone": first_result.get("timezone", "UTC")
    }


# ==============================================================================
# Weather Forecast Fetching: Coordinates -> Raw Forecast Data
# ==============================================================================

def fetch_open_meteo_forecast(
    latitude: float,
    longitude: float,
    timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    Retrieves current weather and upcoming hourly forecasts from Open-Meteo.
    
    Args:
        latitude: Geographic latitude in decimal degrees.
        longitude: Geographic longitude in decimal degrees.
        timeout: Request timeout duration in seconds.
        
    Returns:
        Raw dictionary response from Open-Meteo.
        
    Raises:
        NetworkTimeoutError: On network timeout.
        APIConnectionError: On socket/connection failure.
        APIResponseError: On HTTP error codes or malformed JSON.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "wind_speed_10m"
        ],
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "weather_code",
            "wind_speed_10m"
        ],
        "forecast_days": 2
    }
    
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise NetworkTimeoutError("Connection timed out while fetching weather forecast.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise APIConnectionError("Failed to connect to weather forecast service. Check internet connection.") from exc
    except requests.exceptions.HTTPError as exc:
        raise APIResponseError(f"Weather forecast service returned HTTP error {response.status_code}.") from exc
    except json.JSONDecodeError as exc:
        raise APIResponseError("Weather forecast service returned an invalid JSON response.") from exc


# ==============================================================================
# Data Normalization: Raw Open-Meteo -> Unified Project Data Model
# ==============================================================================

def normalize_live_response(raw_data: Dict[str, Any], geo_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms raw Open-Meteo JSON into the standardized application data model.
    Guarantees consistent keys, units, and nested structures.
    """
    current_raw = raw_data.get("current", {})
    hourly_raw = raw_data.get("hourly", {})
    
    # Extract current weather observations (preserving None for missing values)
    current_code = current_raw.get("weather_code")
    current_temp = float(current_raw["temperature_2m"]) if current_raw.get("temperature_2m") is not None else None
    current_humidity = float(current_raw["relative_humidity_2m"]) if current_raw.get("relative_humidity_2m") is not None else None
    current_wind = float(current_raw["wind_speed_10m"]) if current_raw.get("wind_speed_10m") is not None else None
    current_precip = float(current_raw["precipitation"]) if current_raw.get("precipitation") is not None else None
    
    # Process hourly forecast intervals
    timestamps = hourly_raw.get("time", [])
    temps = hourly_raw.get("temperature_2m", [])
    humidities = hourly_raw.get("relative_humidity_2m", [])
    rain_probs = hourly_raw.get("precipitation_probability", [])
    precips = hourly_raw.get("precipitation", [])
    wind_speeds = hourly_raw.get("wind_speed_10m", [])
    weather_codes = hourly_raw.get("weather_code", [])
    
    # Match rain probability for current observation if available
    current_rain_prob = float(rain_probs[0]) if (rain_probs and len(rain_probs) > 0 and rain_probs[0] is not None) else None

    forecast_intervals: List[Dict[str, Any]] = []
    num_intervals = min(
        len(timestamps),
        len(temps),
        len(humidities),
        len(rain_probs),
        len(wind_speeds)
    )
    
    for i in range(num_intervals):
        w_code = weather_codes[i] if i < len(weather_codes) else None
        forecast_intervals.append({
            "timestamp": timestamps[i],
            "temperature": float(temps[i]) if temps[i] is not None else None,
            "humidity": float(humidities[i]) if humidities[i] is not None else None,
            "precipitation_probability": float(rain_probs[i]) if rain_probs[i] is not None else None,
            "precipitation_amount": float(precips[i]) if (precips and i < len(precips) and precips[i] is not None) else None,
            "wind_speed": float(wind_speeds[i]) if wind_speeds[i] is not None else None,
            "weather_code": int(w_code) if w_code is not None else None,
            "weather_condition": translate_wmo_code(w_code)
        })

    return {
        "data_source": "LIVE",
        "is_simulated": False,
        "city": geo_info.get("city", "Unknown City"),
        "country": geo_info.get("country", "Unknown Country"),
        "coordinates": {
            "latitude": geo_info.get("latitude", 0.0),
            "longitude": geo_info.get("longitude", 0.0)
        },
        "timezone": raw_data.get("timezone", geo_info.get("timezone", "UTC")),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "units": {
            "temperature": "°C",
            "humidity": "%",
            "wind_speed": "km/h",
            "precipitation_amount": "mm",
            "precipitation_probability": "%"
        },
        "current": {
            "timestamp": current_raw.get("time", datetime.now(timezone.utc).isoformat()),
            "temperature": current_temp,
            "humidity": current_humidity,
            "wind_speed": current_wind,
            "precipitation_probability": current_rain_prob,
            "precipitation_amount": current_precip,
            "weather_code": current_code,
            "weather_condition": translate_wmo_code(current_code)
        },
        "forecast": forecast_intervals
    }


# ==============================================================================
# Simulation Loader: Load Offline Fixtures Seamlessly
# ==============================================================================

def load_simulation_data(
    scenario_id: str = "normal_weather",
    data_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Loads an offline simulation scenario from sample_weather.json and sample_forecast.json.
    Ensures zero internet dependency and maintains exact schema compatibility.
    
    Args:
        scenario_id: One of 'normal_weather', 'extreme_heat', 'heavy_rainfall',
                     'strong_winds', 'high_humidity', 'compound_risks'.
        data_dir: Optional custom path to data directory.
        
    Returns:
        Standardized weather dictionary marked with data_source='SIMULATED'.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        
    weather_file = data_dir / "sample_weather.json"
    forecast_file = data_dir / "sample_forecast.json"
    
    if not weather_file.exists() or not forecast_file.exists():
        raise FileNotFoundError(f"Simulation fixtures not found in directory: {data_dir}")
        
    with open(weather_file, "r", encoding="utf-8") as f:
        weather_payload = json.load(f)
        
    with open(forecast_file, "r", encoding="utf-8") as f:
        forecast_payload = json.load(f)
        
    scenarios = weather_payload.get("scenarios", {})
    if scenario_id not in scenarios:
        valid_ids = list(scenarios.keys())
        raise ValueError(f"Scenario '{scenario_id}' not found. Available scenarios: {valid_ids}")
        
    scenario_data = scenarios[scenario_id]
    forecast_entry = forecast_payload.get("forecasts", {}).get(scenario_id, {})
    intervals = forecast_entry.get("intervals", [])
    
    current = scenario_data.get("current", {})
    
    return {
        "data_source": "SIMULATED",
        "is_simulated": True,
        "scenario_id": scenario_id,
        "scenario_name": scenario_data.get("scenario_name", scenario_id),
        "city": scenario_data.get("city", "Simulated City"),
        "country": scenario_data.get("country", "Simulated Country"),
        "coordinates": scenario_data.get("coordinates", {"latitude": 0.0, "longitude": 0.0}),
        "timezone": "UTC+05:30",
        "retrieved_at": scenario_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "units": {
            "temperature": "°C",
            "humidity": "%",
            "wind_speed": "km/h",
            "precipitation_amount": "mm",
            "precipitation_probability": "%"
        },
        "current": {
            "timestamp": scenario_data.get("timestamp"),
            "temperature": current.get("temperature", 0.0),
            "humidity": current.get("humidity", 0.0),
            "wind_speed": current.get("wind_speed", 0.0),
            "precipitation_probability": current.get("precipitation_probability", 0.0),
            "precipitation_amount": current.get("precipitation_amount", 0.0),
            "weather_code": current.get("weather_code", 0),
            "weather_condition": current.get("weather_condition", "Simulated Condition"),
            "expected_alerts": current.get("expected_alerts", [])
        },
        "forecast": intervals
    }


# ==============================================================================
# Unified Master Client Function
# ==============================================================================

def get_weather_data(
    city_name: str = "Mangaluru",
    use_simulation: bool = False,
    scenario_id: str = "normal_weather",
    timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    Unified entry point for retrieving weather data.
    
    If use_simulation is True, loads from offline fixtures.
    If use_simulation is False, calls geocoding and live Open-Meteo forecast API.
    
    Returns:
        Normalized dictionary compliant with project schema.
    """
    if use_simulation:
        logger.info(f"Retrieving simulated weather scenario: '{scenario_id}'")
        return load_simulation_data(scenario_id=scenario_id)
        
    logger.info(f"Retrieving live weather for city: '{city_name}'")
    geo_info = geocode_city(city_name=city_name, timeout=timeout)
    raw_forecast = fetch_open_meteo_forecast(
        latitude=geo_info["latitude"],
        longitude=geo_info["longitude"],
        timeout=timeout
    )
    return normalize_live_response(raw_data=raw_forecast, geo_info=geo_info)
