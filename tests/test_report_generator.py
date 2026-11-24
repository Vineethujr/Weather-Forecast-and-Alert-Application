"""
Unit tests for src/report_generator.py.
Verifies CSV creation and appending, header single-write guarantee,
missing-value preservation, timezone consistency, atomic JSON reporting,
NumPy/Pandas serialization, report loading, and filename sanitization.
All tests use pytest tmp_path to avoid modifying project directories.
"""

import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.alert_system import evaluate_weather_alerts
from src.data_processing import process_weather_payload
from src.forecast_analysis import generate_forecast_summary
from src.report_generator import (
    CSV_MANDATORY_COLUMNS,
    ReportGenerationError,
    append_weather_observation,
    generate_json_report,
    generate_weather_report,
    load_weather_report,
    sanitize_filename_part,
)
from src.weather_api import get_weather_data


# ==============================================================================
# CSV Observation History Tests
# ==============================================================================

def test_csv_creation_and_header(tmp_path):
    """Verify CSV is created with exact mandatory header columns."""
    csv_file = tmp_path / "weather_reports.csv"
    current_data = {
        "city": "Mangaluru",
        "timestamp": "2026-11-24T14:00:00+05:30",
        "temperature_c": 28.5,
        "humidity_pct": 65.0,
        "wind_speed_kmh": 14.0,
        "rain_probability_pct": 10.0,
        "weather_condition": "Partly Cloudy",
        "data_source": "SIMULATED"
    }

    result_path = append_weather_observation(current_data, csv_path=csv_file)
    assert result_path.exists()

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == CSV_MANDATORY_COLUMNS
        row = next(reader)
        assert row[0] == "Mangaluru"
        assert row[1] == "2026-11-24T14:00:00+05:30"
        assert row[2] == "28.5"
        assert row[8] == "SIMULATED"


def test_csv_append_without_overwriting(tmp_path):
    """Verify appending multiple observations preserves historical records."""
    csv_file = tmp_path / "weather_reports.csv"

    obs1 = {"city": "Mangaluru", "temperature_c": 28.0, "data_source": "SIMULATED"}
    obs2 = {"city": "Mumbai", "temperature_c": 32.0, "data_source": "LIVE"}

    append_weather_observation(obs1, csv_path=csv_file)
    append_weather_observation(obs2, csv_path=csv_file)

    with open(csv_file, mode="r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # 1 Header row + 2 Data rows
    assert len(rows) == 3
    assert rows[0] == CSV_MANDATORY_COLUMNS
    assert rows[1][0] == "Mangaluru"
    assert rows[2][0] == "Mumbai"


def test_csv_header_written_only_once(tmp_path):
    """Verify header is never duplicated during sequential appends."""
    csv_file = tmp_path / "weather_reports.csv"

    for i in range(3):
        append_weather_observation(
            {"city": f"City_{i}", "temperature_c": 20.0 + i},
            csv_path=csv_file
        )

    with open(csv_file, mode="r", encoding="utf-8") as f:
        content = f.read()

    # The header line should appear exactly once
    header_str = ",".join(CSV_MANDATORY_COLUMNS)
    assert content.count(header_str) == 1


def test_csv_missing_measurements_preserved_as_empty(tmp_path):
    """Verify missing values are serialized as empty strings, not zero."""
    csv_file = tmp_path / "weather_reports.csv"
    current_data = {
        "city": "MissingSensorsCity",
        "temperature_c": None,  # Missing temperature
        "humidity_pct": np.nan,  # NaN humidity
        "wind_speed_kmh": "",     # Empty string
        "rain_probability_pct": None,
        "data_source": "LIVE"
    }

    append_weather_observation(current_data, csv_path=csv_file)

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

        assert row["temperature"] == ""
        assert row["humidity"] == ""
        assert row["wind_speed"] == ""
        assert row["rain_probability"] == ""
        # Guarantee it was not coerced to 0 or 0.0
        assert row["temperature"] != "0"
        assert row["temperature"] != "0.0"


def test_csv_alert_messages_serialization(tmp_path):
    """Verify active alert messages are formatted cleanly into the alert_messages column."""
    csv_file = tmp_path / "weather_reports.csv"
    current_data = {"city": "Delhi", "temperature_c": 44.0, "data_source": "SIMULATED"}
    alerts = [
        {"message": "[WARNING] High Temperature Alert for Delhi"},
        {"message": "[WATCH] High Humidity Alert"}
    ]

    append_weather_observation(current_data, alerts=alerts, csv_path=csv_file)

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert "[WARNING] High Temperature Alert" in row["alert_messages"]
        assert "[WATCH] High Humidity Alert" in row["alert_messages"]
        assert " | " in row["alert_messages"]


# ==============================================================================
# JSON Audit Report Tests
# ==============================================================================

def test_json_report_creation_and_structure(tmp_path):
    """Verify JSON report generation with metadata, observations, forecast, and alerts."""
    raw = get_weather_data(use_simulation=True, scenario_id="extreme_heat")
    bundle = process_weather_payload(raw)
    stats = generate_forecast_summary(bundle["forecast_df"], metadata=bundle)
    alerts = evaluate_weather_alerts(bundle["current"], bundle["forecast_df"], metadata=bundle)

    report_path = generate_json_report(
        weather_bundle=bundle,
        forecast_summary=stats,
        alert_report=alerts,
        output_dir=tmp_path
    )

    assert report_path.exists()
    assert report_path.suffix == ".json"

    with open(report_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Core sections
    assert "metadata" in payload
    assert "current_weather" in payload
    assert "forecast_intervals" in payload
    assert "forecast_analysis" in payload
    assert "alerts" in payload

    # Metadata checks
    meta = payload["metadata"]
    assert meta["city"] == "Delhi"
    assert meta["data_source"] == "SIMULATED"
    assert meta["is_simulated"] is True
    assert "disclaimer" in meta
    assert "not official meteorological warnings" in meta["disclaimer"]

    # Forecast intervals serialized as JSON array of dicts
    assert isinstance(payload["forecast_intervals"], list)
    assert len(payload["forecast_intervals"]) == 8


def test_json_serialization_numpy_and_pandas_types(tmp_path):
    """Verify NumPy scalars and NaN/None values serialize without TypeError."""
    custom_bundle = {
        "city": "SerializationTestCity",
        "data_source": "LIVE",
        "is_simulated": False,
        "current": {
            "temp_np_float": np.float64(31.4),
            "wind_np_int": np.int64(24),
            "missing_nan": np.nan,
            "timestamp": pd.Timestamp("2026-11-24T12:00:00Z")
        },
        "forecast_df": pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-11-24 12:00:00Z")],
            "temp": [np.float64(28.0)],
            "missing": [np.nan]
        })
    }

    report_path = generate_json_report(custom_bundle, output_dir=tmp_path)
    assert report_path.exists()

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["current_weather"]["temp_np_float"] == 31.4
    assert data["current_weather"]["wind_np_int"] == 24
    assert data["current_weather"]["missing_nan"] is None


def test_load_weather_report(tmp_path):
    """Verify loading a previously generated report file."""
    custom_bundle = {"city": "LoadTestCity", "data_source": "SIMULATED"}
    report_path = generate_json_report(custom_bundle, output_dir=tmp_path, filename="test_report.json")

    loaded = load_weather_report(report_path)
    assert loaded["metadata"]["city"] == "LoadTestCity"
    assert loaded["metadata"]["data_source"] == "SIMULATED"


def test_load_weather_report_missing_file():
    """Verify FileNotFoundError when loading a non-existent report."""
    with pytest.raises(FileNotFoundError):
        load_weather_report(Path("non_existent_report_12345.json"))


# ==============================================================================
# Safety & Edge Case Tests
# ==============================================================================

def test_sanitize_filename_part():
    """Verify filename sanitization prevents path traversal and special character corruption."""
    assert sanitize_filename_part("Mangaluru") == "mangaluru"
    assert sanitize_filename_part("Kochi Coastal Harbor") == "kochi_coastal_harbor"
    assert sanitize_filename_part("../../evil/path") == "evil_path"
    assert sanitize_filename_part("City:Name/With*Chars?") == "city_name_with_chars"
    assert sanitize_filename_part("   ") == "unnamed"


def test_master_generate_weather_report(tmp_path):
    """Verify master coordinator creates both CSV entry and JSON report."""
    raw = get_weather_data(use_simulation=True, scenario_id="normal_weather")
    bundle = process_weather_payload(raw)
    stats = generate_forecast_summary(bundle["forecast_df"], metadata=bundle)
    alerts = evaluate_weather_alerts(bundle["current"], bundle["forecast_df"], metadata=bundle)

    result = generate_weather_report(
        weather_bundle=bundle,
        forecast_summary=stats,
        alert_report=alerts,
        reports_dir=tmp_path
    )

    assert "csv_report" in result
    assert "json_report" in result
    assert result["csv_report"].exists()
    assert result["json_report"].exists()


def test_invalid_input_raises_report_generation_error():
    """Verify malformed input raises ReportGenerationError."""
    with pytest.raises(ReportGenerationError):
        append_weather_observation(None)

    with pytest.raises(ReportGenerationError):
        generate_json_report(None)
