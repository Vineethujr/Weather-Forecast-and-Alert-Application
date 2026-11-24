"""
Unit tests for src/alert_system.py.
Verifies configurable alert rules, threshold evaluations, severity classifications,
compound multi-hazard detection, duplicate suppression, resilient null-handling,
and non-official disclaimer enforcement.
"""

import pandas as pd
import pytest

from src.alert_system import (
    OFFICIAL_WARNING_DISCLAIMER,
    AlertThresholds,
    classify_severity,
    evaluate_current_weather_alerts,
    evaluate_forecast_alerts,
    evaluate_single_condition,
    evaluate_weather_alerts,
)
from src.data_processing import process_weather_payload
from src.weather_api import get_weather_data


# ==============================================================================
# Severity Classification Tests
# ==============================================================================

def test_classify_severity_temperature():
    """Verify temperature severity tiers (Advisory, Watch, Warning)."""
    # Threshold = 40.0
    assert classify_severity("High Temperature Alert", 41.5, 40.0) == "Advisory"
    assert classify_severity("High Temperature Alert", 44.0, 40.0) == "Watch"
    assert classify_severity("High Temperature Alert", 47.5, 40.0) == "Warning"


def test_classify_severity_humidity():
    """Verify humidity severity tiers."""
    assert classify_severity("High Humidity Alert", 88.0, 85.0) == "Advisory"
    assert classify_severity("High Humidity Alert", 92.0, 85.0) == "Watch"
    assert classify_severity("High Humidity Alert", 98.0, 85.0) == "Warning"


def test_classify_severity_rain():
    """Verify rain probability severity tiers."""
    assert classify_severity("Rain Alert", 75.0, 70.0) == "Advisory"
    assert classify_severity("Rain Alert", 85.0, 70.0) == "Watch"
    assert classify_severity("Rain Alert", 95.0, 70.0) == "Warning"


def test_classify_severity_wind():
    """Verify wind speed severity tiers."""
    assert classify_severity("High Wind Alert", 58.0, 50.0) == "Advisory"
    assert classify_severity("High Wind Alert", 72.0, 50.0) == "Watch"
    assert classify_severity("High Wind Alert", 90.0, 50.0) == "Warning"


# ==============================================================================
# Single Condition Evaluation Tests
# ==============================================================================

def test_evaluate_single_condition_triggered():
    """Verify alert dictionary generated when measurement breaches threshold."""
    alert = evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=42.5,
        threshold=40.0,
        unit="°C",
        timestamp="2026-11-24T14:00:00+05:30",
        city="Delhi",
        data_source="LIVE",
        is_simulated=False
    )
    assert alert is not None
    assert alert["alert_type"] == "High Temperature Alert"
    assert alert["measured_value"] == 42.5
    assert alert["threshold"] == 40.0
    assert alert["severity"] in ["Advisory", "Watch", "Warning"]
    assert alert["city"] == "Delhi"
    assert alert["data_source"] == "LIVE"
    assert alert["is_simulated"] is False
    assert "exceeds configurable threshold" in alert["message"]


def test_evaluate_single_condition_not_triggered():
    """Verify no alert is generated when measurement is below or equal to threshold."""
    assert evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=35.0,
        threshold=40.0,
        unit="°C",
        timestamp="2026-11-24",
        city="Mangaluru",
        data_source="LIVE",
        is_simulated=False
    ) is None

    # Equal to threshold does not breach (> threshold)
    assert evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=40.0,
        threshold=40.0,
        unit="°C",
        timestamp="2026-11-24",
        city="Mangaluru",
        data_source="LIVE",
        is_simulated=False
    ) is None


def test_evaluate_single_condition_none_or_nan():
    """Verify None or NaN measurements never trigger an alert."""
    assert evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=None,
        threshold=40.0,
        unit="°C",
        timestamp="2026-11-24",
        city="City",
        data_source="LIVE",
        is_simulated=False
    ) is None

    assert evaluate_single_condition(
        alert_type="High Temperature Alert",
        measured_value=float("nan"),
        threshold=40.0,
        unit="°C",
        timestamp="2026-11-24",
        city="City",
        data_source="LIVE",
        is_simulated=False
    ) is None


# ==============================================================================
# Simulation Scenario Alert Tests
# ==============================================================================

def test_alerts_normal_weather_no_alerts():
    """Verify normal mild weather scenario triggers zero alerts."""
    raw = get_weather_data(use_simulation=True, scenario_id="normal_weather")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is False
    assert result["total_alerts"] == 0
    assert result["is_compound_risk"] is False
    assert result["highest_severity"] is None
    assert "within normal thresholds" in result["summary"]


def test_alerts_extreme_heat_scenario():
    """Verify extreme heat scenario triggers high temperature alert."""
    raw = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is True
    assert "High Temperature Alert" in result["triggered_types"]
    assert result["highest_severity"] in ["Watch", "Warning"]


def test_alerts_heavy_rainfall_scenario():
    """Verify heavy rainfall scenario triggers rain and humidity alerts."""
    raw = get_weather_data(use_simulation=True, scenario_id="heavy_rainfall")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is True
    assert "Rain Alert" in result["triggered_types"]
    assert "High Humidity Alert" in result["triggered_types"]
    assert result["is_compound_risk"] is True


def test_alerts_strong_winds_scenario():
    """Verify strong winds scenario triggers high wind alert."""
    raw = get_weather_data(use_simulation=True, scenario_id="strong_winds")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is True
    assert "High Wind Alert" in result["triggered_types"]


def test_alerts_high_humidity_scenario():
    """Verify high humidity scenario triggers humidity alert."""
    raw = get_weather_data(use_simulation=True, scenario_id="high_humidity")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is True
    assert "High Humidity Alert" in result["triggered_types"]


def test_alerts_compound_risks_all_alerts():
    """Verify compound multi-hazard scenario triggers all 4 alert conditions simultaneously."""
    raw = get_weather_data(use_simulation=True, scenario_id="compound_risks")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(
        current_data=bundle["current"],
        forecast_df=bundle["forecast_df"],
        metadata=bundle
    )

    assert result["has_alerts"] is True
    assert result["is_compound_risk"] is True
    assert set(result["triggered_types"]) == {
        "High Temperature Alert",
        "High Humidity Alert",
        "Rain Alert",
        "High Wind Alert"
    }
    assert result["highest_severity"] == "Warning"


# ==============================================================================
# Deduplication & Forecast Intervals Tests
# ==============================================================================

def test_evaluate_forecast_alerts_duplicate_prevention():
    """Verify duplicate alerts for the same condition at the same timestamp are suppressed."""
    duplicate_df = pd.DataFrame({
        "timestamp": [
            pd.Timestamp("2026-11-24 12:00"),
            pd.Timestamp("2026-11-24 12:00")  # Duplicate timestamp with high temperature
        ],
        "temperature_c": [45.0, 45.0],
        "humidity_pct": [50.0, 50.0],
        "rain_probability_pct": [10.0, 10.0],
        "wind_speed_kmh": [15.0, 15.0]
    })
    alerts = evaluate_forecast_alerts(duplicate_df)
    # Only 1 temperature alert should be emitted, duplicate suppressed
    temp_alerts = [a for a in alerts if a["alert_type"] == "High Temperature Alert"]
    assert len(temp_alerts) == 1


def test_evaluate_forecast_alerts_different_timestamps():
    """Verify alerts at different timestamps are both captured."""
    multi_df = pd.DataFrame({
        "timestamp": [
            pd.Timestamp("2026-11-24 12:00"),
            pd.Timestamp("2026-11-24 15:00")
        ],
        "temperature_c": [43.0, 44.0],
        "humidity_pct": [50.0, 50.0],
        "rain_probability_pct": [10.0, 10.0],
        "wind_speed_kmh": [15.0, 15.0]
    })
    alerts = evaluate_forecast_alerts(multi_df)
    temp_alerts = [a for a in alerts if a["alert_type"] == "High Temperature Alert"]
    assert len(temp_alerts) == 2


def test_evaluate_forecast_alerts_empty_df():
    """Verify empty forecast DataFrame produces zero alerts without error."""
    assert evaluate_forecast_alerts(pd.DataFrame()) == []
    assert evaluate_forecast_alerts(None) == []


# ==============================================================================
# Configurable Thresholds & Disclaimer Tests
# ==============================================================================

def test_custom_thresholds_override():
    """Verify custom thresholds adjust alert triggering sensitivity."""
    current_data = {
        "city": "TestCity",
        "timestamp": "2026-11-24 12:00",
        "temperature_c": 36.0,  # Below default 40.0°C, but above custom 35.0°C
        "humidity_pct": 50.0,
        "wind_speed_kmh": 20.0,
        "rain_probability_pct": 10.0
    }
    # Default thresholds -> No alert
    default_res = evaluate_weather_alerts(current_data)
    assert default_res["has_alerts"] is False

    # Custom thresholds -> Alert triggers
    custom_thresholds = AlertThresholds(high_temp_c=35.0)
    custom_res = evaluate_weather_alerts(current_data, thresholds=custom_thresholds)
    assert custom_res["has_alerts"] is True
    assert "High Temperature Alert" in custom_res["triggered_types"]


def test_disclaimer_presence():
    """Verify official warning disclaimer is present in every alert report."""
    raw = get_weather_data(use_simulation=True, scenario_id="normal_weather")
    bundle = process_weather_payload(raw)
    result = evaluate_weather_alerts(bundle["current"], bundle["forecast_df"])

    assert "disclaimer" in result
    assert result["disclaimer"] == OFFICIAL_WARNING_DISCLAIMER
    assert "not official meteorological warnings" in result["disclaimer"]
