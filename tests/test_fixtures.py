"""
Unit tests for simulation fixtures integrity.
Verifies that sample_weather.json and sample_forecast.json comply with expected schemas.
"""

import json
from pathlib import Path

def test_simulation_fixtures_schema():
    """Verify that both sample_weather.json and sample_forecast.json meet schema requirements."""
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    
    weather_file = data_dir / "sample_weather.json"
    forecast_file = data_dir / "sample_forecast.json"
    
    assert weather_file.exists(), f"File missing: {weather_file}"
    assert forecast_file.exists(), f"File missing: {forecast_file}"
    
    # 1. Validate sample_weather.json
    with open(weather_file, "r", encoding="utf-8") as f:
        wdata = json.load(f)
        
    assert wdata.get("metadata", {}).get("data_source") == "SIMULATED"
    assert wdata.get("metadata", {}).get("is_simulated") is True
    
    expected_scenarios = [
        "normal_weather",
        "extreme_heat",
        "heavy_rainfall",
        "strong_winds",
        "high_humidity",
        "compound_risks"
    ]
    
    scenarios = wdata.get("scenarios", {})
    for s_id in expected_scenarios:
        assert s_id in scenarios, f"Scenario '{s_id}' missing in sample_weather.json"
        s = scenarios[s_id]
        assert s["data_source"] == "SIMULATED"
        assert s["is_simulated"] is True
        
        cur = s["current"]
        assert isinstance(cur["temperature"], (int, float))
        assert 0 <= cur["humidity"] <= 100
        assert 0 <= cur["precipitation_probability"] <= 100
        assert cur["wind_speed"] >= 0
        assert isinstance(cur.get("expected_alerts"), list)

    # 2. Validate sample_forecast.json
    with open(forecast_file, "r", encoding="utf-8") as f:
        fdata = json.load(f)
        
    assert fdata.get("metadata", {}).get("data_source") == "SIMULATED"
    assert fdata.get("metadata", {}).get("is_simulated") is True
    
    forecasts = fdata.get("forecasts", {})
    for s_id in expected_scenarios:
        assert s_id in forecasts, f"Forecast scenario '{s_id}' missing in sample_forecast.json"
        fc = forecasts[s_id]
        assert fc["data_source"] == "SIMULATED"
        assert fc["is_simulated"] is True
        
        intervals = fc.get("intervals", [])
        assert len(intervals) == 8, f"Expected 8 forecast intervals for {s_id}"
        
        for it in intervals:
            assert "timestamp" in it
            assert isinstance(it["temperature"], (int, float))
            assert 0 <= it["humidity"] <= 100
            assert 0 <= it["precipitation_probability"] <= 100
            assert it["wind_speed"] >= 0
