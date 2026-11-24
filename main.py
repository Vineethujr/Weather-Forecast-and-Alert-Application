"""
Weather Forecast & Alert Application - Command-Line Interface (CLI).
Interactive terminal entry point for live meteorological tracking, offline scenario simulation,
statistical summaries, configurable alert monitoring, chart generation, and report persistence.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from src.weather_api import (
    APIConnectionError,
    APIResponseError,
    CityNotFoundError,
    NetworkTimeoutError,
)
from src.weather_service import AVAILABLE_SCENARIOS, execute_weather_workflow

DIVIDER = "=" * 76
SUB_DIVIDER = "-" * 76


def print_banner() -> None:
    """Displays the application startup banner."""
    print("\n" + DIVIDER)
    print("      WEATHER FORECAST & ALERT APPLICATION (Industry Standard CLI)      ")
    print("      Real-Time Meteorological Monitoring & Predictive Alert Engine     ")
    print(DIVIDER)


def print_current_weather_card(data: Dict[str, Any]) -> None:
    """Renders a formatted ASCII weather observation card."""
    current = data["current"]
    badge = "[SIMULATED DATA]" if data["is_simulated"] else "[LIVE OBSERVATION]"
    ts_str = str(current.get("timestamp", "Current Time"))

    print("\n" + SUB_DIVIDER)
    print(f"CURRENT WEATHER OBSERVATION: {data['city']}, {data['country']}  {badge}")
    print(SUB_DIVIDER)
    print(f"  Observation Time  : {ts_str}")
    print(f"  Weather Condition : {current.get('weather_condition', 'N/A')}")
    
    t_val = current.get("temperature_c")
    print(f"  Temperature       : {t_val:.1f} °C" if t_val is not None else "  Temperature       : N/A")
    
    h_val = current.get("humidity_pct")
    print(f"  Relative Humidity : {h_val:.0f} %" if h_val is not None else "  Relative Humidity : N/A")
    
    w_val = current.get("wind_speed_kmh")
    print(f"  Wind Speed        : {w_val:.1f} km/h" if w_val is not None else "  Wind Speed        : N/A")
    
    r_val = current.get("rain_probability_pct")
    print(f"  Rain Probability  : {r_val:.0f} %" if r_val is not None else "  Rain Probability  : N/A")
    
    p_val = current.get("precipitation_mm")
    if p_val is not None and p_val > 0:
        print(f"  Precipitation     : {p_val:.1f} mm")
    print(SUB_DIVIDER)


def print_forecast_table(data: Dict[str, Any]) -> None:
    """Renders upcoming forecast intervals in a clean terminal table."""
    df = data.get("forecast_df")
    print("\n" + SUB_DIVIDER)
    print("UPCOMING FORECAST HORIZON")
    print(SUB_DIVIDER)

    if df is None or df.empty:
        print("  No forecast intervals available.")
        print(SUB_DIVIDER)
        return

    # Header
    print(f"{'Timestamp':<20} | {'Temp (°C)':<9} | {'Humidity':<8} | {'Rain Prob':<9} | {'Precip (mm)':<11} | {'Wind (km/h)':<11} | {'Condition'}")
    print("-" * 105)

    for _, row in df.iterrows():
        ts_raw = row.get("timestamp")
        ts_fmt = str(ts_raw)[:16] if pd_not_na(ts_raw) else "N/A"
        
        t = f"{row['temperature_c']:.1f}" if pd_not_na(row.get("temperature_c")) else "N/A"
        h = f"{row['humidity_pct']:.0f}%" if pd_not_na(row.get("humidity_pct")) else "N/A"
        r = f"{row['rain_probability_pct']:.0f}%" if pd_not_na(row.get("rain_probability_pct")) else "N/A"
        p = f"{row['precipitation_mm']:.1f}" if pd_not_na(row.get("precipitation_mm")) else "0.0"
        w = f"{row['wind_speed_kmh']:.1f}" if pd_not_na(row.get("wind_speed_kmh")) else "N/A"
        cond = str(row.get("weather_condition", "N/A"))

        print(f"{ts_fmt:<20} | {t:>9} | {h:>8} | {r:>9} | {p:>11} | {w:>11} | {cond}")

    print(SUB_DIVIDER)


def pd_not_na(val: Any) -> bool:
    """Checks if a value is not None/NaN."""
    if val is None:
        return False
    try:
        import pandas as pd
        return not pd.isna(val)
    except Exception:
        return True


def print_statistical_summary(data: Dict[str, Any]) -> None:
    """Displays forecast statistical analysis, temperature trend, and peak intervals."""
    summary = data.get("forecast_summary", {})
    stats = summary.get("statistics", {})
    trend = summary.get("temperature_trend", {})
    peaks = summary.get("peak_intervals", {})

    print("\n" + SUB_DIVIDER)
    print("FORECAST STATISTICAL ANALYSIS & TRENDS")
    print(SUB_DIVIDER)

    overview = summary.get("overview")
    if overview:
        print(f"Overview: {overview}\n")

    # Metrics
    t_stats = stats.get("temperature", {})
    h_stats = stats.get("humidity", {})
    w_stats = stats.get("wind_speed", {})
    p_stats = stats.get("precipitation", {})

    print(f"  • Temperature Range : Min {t_stats.get('min')}°C | Max {t_stats.get('max')}°C | Average {t_stats.get('mean')}°C")
    print(f"  • Temperature Trend : {trend.get('trend', 'Undetermined')} ({trend.get('reason', '')})")
    print(f"  • Relative Humidity : Min {h_stats.get('min')}% | Max {h_stats.get('max')}% | Average {h_stats.get('mean')}%")
    print(f"  • Wind Velocities   : Min {w_stats.get('min')} km/h | Max Sustained {w_stats.get('max')} km/h | Peak Gust {w_stats.get('max_gust')} km/h")
    print(f"  • Rainfall Outlook  : Peak Probability {p_stats.get('max_probability')}% | Expected Cumulative {p_stats.get('cumulative_amount_mm')} mm")

    # Peaks
    if peaks.get("peak_temperature"):
        pt = peaks["peak_temperature"]
        print(f"\n  Peak Temperature    : {pt['value']}°C at {pt['timestamp']} ({pt['condition']})")
    if peaks.get("peak_rain_probability"):
        pr = peaks["peak_rain_probability"]
        print(f"  Peak Rain Likelihood: {pr['value']}% at {pr['timestamp']} ({pr['condition']})")
    if peaks.get("peak_wind_speed"):
        pw = peaks["peak_wind_speed"]
        print(f"  Peak Wind Speed     : {pw['value']} km/h at {pw['timestamp']} ({pw['condition']})")

    print(SUB_DIVIDER)


def print_alert_center(data: Dict[str, Any]) -> None:
    """Displays active rule-based alerts, compound risk notices, and non-official disclaimers."""
    alert_report = data.get("alert_report", {})
    has_alerts = alert_report.get("has_alerts", False)
    total_alerts = alert_report.get("total_alerts", 0)
    all_alerts = alert_report.get("all_alerts", [])
    disclaimer = alert_report.get("disclaimer", "")

    print("\n" + DIVIDER)
    print("                     WEATHER ALERT MONITORING CENTER                    ")
    print(DIVIDER)

    if not has_alerts:
        print("\n  [STATUS: NORMAL] All weather parameters are currently within safe limits.")
        print("  No active alerts detected.")
    else:
        compound = " *** COMPOUND MULTI-HAZARD RISK DETECTED ***" if alert_report.get("is_compound_risk") else ""
        highest = alert_report.get("highest_severity", "Advisory")
        print(f"\n  [STATUS: ACTIVE ALERTS ({total_alerts})]{compound}")
        print(f"  Highest Application Severity: {highest}")
        print(f"  Triggered Conditions: {', '.join(alert_report.get('triggered_types', []))}\n")

        for idx, alert in enumerate(all_alerts, 1):
            sev_pill = f"[{alert['severity'].upper()}]"
            print(f"  {idx}. {sev_pill:<10} {alert['alert_type']:<24} | Value: {alert['measured_value']}{alert['unit']} (Threshold: {alert['threshold']}{alert['unit']})")
            print(f"     Time: {alert['timestamp']} ({alert['context_label']})")
            print(f"     Details: {alert['message']}\n")

    print(SUB_DIVIDER)
    print("SAFETY DISCLAIMER:")
    print(f"  {disclaimer}")
    print(DIVIDER)


def print_generated_outputs(data: Dict[str, Any]) -> None:
    """Lists saved visualization charts and persistent reports."""
    charts = data.get("charts", {})
    reports = data.get("reports", {})

    print("\n" + SUB_DIVIDER)
    print("AUTOMATIC SYSTEM OUTPUTS GENERATED")
    print(SUB_DIVIDER)

    if charts:
        print("  Generated Visualization Charts (Saved in outputs/):")
        for key, path in charts.items():
            print(f"    • {key.capitalize():<14}: {path.name} (file:///{path.as_posix()})")

    if reports:
        print("\n  Generated Reports (Saved in reports/):")
        for key, path in reports.items():
            print(f"    • {key.replace('_', ' ').capitalize():<14}: {path.name} (file:///{path.as_posix()})")

    print(SUB_DIVIDER + "\n")


def run_weather_pipeline(
    city_name: str = "Mangaluru",
    use_simulation: bool = False,
    scenario_id: str = "normal_weather"
) -> None:
    """Executes the weather service pipeline and renders CLI screens with full error handling."""
    mode_label = f"Simulated Scenario '{scenario_id}'" if use_simulation else f"Live API for '{city_name}'"
    print(f"\nExecuting weather workflow for: {mode_label}...")

    try:
        results = execute_weather_workflow(
            city_name=city_name,
            use_simulation=use_simulation,
            scenario_id=scenario_id,
            generate_charts=True,
            generate_reports=True
        )
    except CityNotFoundError as exc:
        print(f"\n[ERROR] City Not Found: {exc}")
        print("Please check the city spelling and try again.")
        return
    except NetworkTimeoutError as exc:
        print(f"\n[ERROR] Network Timeout: {exc}")
        print("The weather service took too long to respond. You can switch to Simulation Mode to test offline.")
        return
    except APIConnectionError as exc:
        print(f"\n[ERROR] Connection Failure: {exc}")
        print("Unable to reach the live weather service. Check your internet connection or use Simulation Mode.")
        return
    except APIResponseError as exc:
        print(f"\n[ERROR] API Service Error: {exc}")
        return
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] An error occurred while processing weather data: {exc}")
        return

    # Render formatted outputs
    print_current_weather_card(results)
    print_forecast_table(results)
    print_statistical_summary(results)
    print_alert_center(results)
    print_generated_outputs(results)


def interactive_menu() -> None:
    """Main interactive terminal menu loop."""
    print_banner()

    while True:
        print("\nAPPLICATION MENU:")
        print("  [1] Live Weather API (Fetch live weather for any city)")
        print("  [2] Virtual Weather Simulation (Offline scenario testing)")
        print("  [3] Launch Streamlit Interactive Web Dashboard")
        print("  [4] Exit Application")

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            city = input("\nEnter City Name (e.g. Mangaluru, London, Tokyo, Delhi): ").strip()
            if not city:
                print("[WARNING] City name cannot be empty. Defaulting to 'Mangaluru'.")
                city = "Mangaluru"
            run_weather_pipeline(city_name=city, use_simulation=False)

        elif choice == "2":
            print("\nAVAILABLE OFFLINE SIMULATION SCENARIOS:")
            scenario_keys = list(AVAILABLE_SCENARIOS.keys())
            for idx, key in enumerate(scenario_keys, 1):
                print(f"  [{idx}] {AVAILABLE_SCENARIOS[key]}")

            s_choice = input(f"\nSelect scenario (1-{len(scenario_keys)}): ").strip()
            try:
                s_idx = int(s_choice) - 1
                if 0 <= s_idx < len(scenario_keys):
                    chosen_scenario = scenario_keys[s_idx]
                    run_weather_pipeline(use_simulation=True, scenario_id=chosen_scenario)
                else:
                    print("[ERROR] Invalid choice. Returning to main menu.")
            except ValueError:
                print("[ERROR] Please enter a valid numerical choice.")

        elif choice == "3":
            print("\nLaunching Streamlit Dashboard...")
            print("Command: streamlit run app.py")
            print("To terminate the dashboard server later, press Ctrl+C in its terminal.\n")
            try:
                subprocess.run(["streamlit", "run", "app.py"])
            except Exception as exc:
                print(f"[ERROR] Could not start Streamlit: {exc}")
                print("Run manually in a new terminal: streamlit run app.py")

        elif choice == "4":
            print("\nExiting Weather Forecast & Alert Application. Stay safe and weather-aware!\n")
            sys.exit(0)

        else:
            print("[ERROR] Invalid selection. Please enter 1, 2, 3, or 4.")


def main() -> None:
    """Application CLI entry point supporting both flags and interactive mode."""
    parser = argparse.ArgumentParser(
        description="Weather Forecast & Alert Application - Industry Standard Meteorological Tracker"
    )
    parser.add_argument("--city", type=str, help="City name for live weather tracking")
    parser.add_argument("--simulation", type=str, choices=list(AVAILABLE_SCENARIOS.keys()), help="Scenario ID for offline simulation")
    parser.add_argument("--dashboard", action="store_true", help="Launch the interactive Streamlit dashboard directly")

    args = parser.parse_args()

    if args.dashboard:
        subprocess.run(["streamlit", "run", "app.py"])
        return

    if args.simulation:
        print_banner()
        run_weather_pipeline(use_simulation=True, scenario_id=args.simulation)
    elif args.city:
        print_banner()
        run_weather_pipeline(city_name=args.city, use_simulation=False)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
