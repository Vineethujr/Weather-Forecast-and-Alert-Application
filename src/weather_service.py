"""
Weather Service Orchestration Module.
Central coordinator connecting API client, data processing, forecast analysis,
alert generation, visualization charts, and persistent reporting.
Consumed directly by both the CLI (main.py) and the Streamlit Dashboard (app.py)
to eliminate business logic duplication.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.alert_system import AlertThresholds, evaluate_weather_alerts
from src.data_processing import process_weather_payload
from src.forecast_analysis import generate_forecast_summary
from src.report_generator import generate_weather_report
from src.visualization import generate_all_forecast_charts
from src.weather_api import get_weather_data

logger = logging.getLogger(__name__)

# Available offline simulation scenarios
AVAILABLE_SCENARIOS = {
    "normal_weather": "Normal Mild Weather (Mangaluru)",
    "extreme_heat": "Extreme Heatwave (Delhi)",
    "heavy_rainfall": "Severe Monsoon Downpour (Mumbai)",
    "strong_winds": "Coastal Gale & Strong Winds (Chennai Coast)",
    "high_humidity": "Tropical High Humidity (Kolkata)",
    "compound_risks": "Severe Compound Multi-Hazard Weather (Kochi)",
}


class WeatherServiceError(Exception):
    """Base exception for application workflow orchestration errors."""
    pass


def execute_weather_workflow(
    city_name: str = "Mangaluru",
    use_simulation: bool = False,
    scenario_id: str = "normal_weather",
    thresholds: Optional[AlertThresholds] = None,
    generate_charts: bool = True,
    generate_reports: bool = True,
    output_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Executes the end-to-end weather processing workflow.
    
    Orchestration Sequence:
    1. Retrieve raw data (Live Open-Meteo API or Offline Simulation fixture).
    2. Normalize raw payload into structured dictionary and Pandas DataFrame.
    3. Calculate statistical summaries, temperature trend, and peak intervals.
    4. Evaluate current and forecast measurements against configurable alert rules.
    5. Generate time-series and dashboard charts in outputs/.
    6. Record observation in persistent CSV log and export atomic JSON report.
    
    Args:
        city_name: Name of target city (for live mode).
        use_simulation: Boolean flag to switch between live and simulated data.
        scenario_id: Key of the simulation scenario if use_simulation=True.
        thresholds: Optional custom AlertThresholds instance.
        generate_charts: Whether to render and save Matplotlib PNG charts.
        generate_reports: Whether to save CSV observation and JSON report.
        output_dir: Custom directory for generated charts.
        reports_dir: Custom directory for generated reports.
        timeout: HTTP request timeout in seconds.
        
    Returns:
        Consolidated dictionary with processed data, analysis, alerts, and file paths.
    """
    if thresholds is None:
        thresholds = AlertThresholds.from_env()

    # 1. Fetch raw weather payload
    raw_payload = get_weather_data(
        city_name=city_name,
        use_simulation=use_simulation,
        scenario_id=scenario_id,
        timeout=timeout
    )

    # 2. Process and normalize into DataFrame and typed current observations
    weather_bundle = process_weather_payload(raw_payload)
    current_data = weather_bundle["current"]
    forecast_df = weather_bundle["forecast_df"]

    # 3. Forecast statistical analysis & trend detection
    forecast_summary = generate_forecast_summary(
        df=forecast_df,
        metadata=weather_bundle
    )

    # 4. Configurable alert evaluation
    alert_report = evaluate_weather_alerts(
        current_data=current_data,
        forecast_df=forecast_df,
        thresholds=thresholds,
        metadata=weather_bundle
    )

    # 5. Visualizations
    chart_paths: Dict[str, Path] = {}
    if generate_charts:
        chart_paths = generate_all_forecast_charts(
            df=forecast_df,
            metadata=weather_bundle,
            thresholds=thresholds,
            output_dir=output_dir
        )

    # 6. Report generation & persistence
    report_paths: Dict[str, Path] = {}
    if generate_reports:
        report_paths = generate_weather_report(
            weather_bundle=weather_bundle,
            forecast_summary=forecast_summary,
            alert_report=alert_report,
            reports_dir=reports_dir
        )

    return {
        "city": weather_bundle["city"],
        "country": weather_bundle["country"],
        "coordinates": weather_bundle["coordinates"],
        "timezone": weather_bundle["timezone"],
        "retrieved_at": weather_bundle["retrieved_at"],
        "data_source": weather_bundle["data_source"],
        "is_simulated": weather_bundle["is_simulated"],
        "units": weather_bundle["units"],
        "current": current_data,
        "forecast_df": forecast_df,
        "forecast_summary": forecast_summary,
        "alert_report": alert_report,
        "charts": chart_paths,
        "reports": report_paths,
        "warnings": weather_bundle.get("warnings", []),
    }
