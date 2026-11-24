"""
Weather Forecast & Alert Application - Interactive Streamlit Dashboard.
Real-Time Meteorological Monitoring, Offline Virtual Simulation,
Predictive Alert Center, Dynamic Visualizations, and Report Exports.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.alert_system import AlertThresholds
from src.weather_api import (
    APIConnectionError,
    APIResponseError,
    CityNotFoundError,
    NetworkTimeoutError,
)
from src.weather_service import AVAILABLE_SCENARIOS, execute_weather_workflow

# Streamlit Page Configuration
st.set_page_config(
    page_title="Weather Forecast & Alert Application",
    page_icon="⛅",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==============================================================================
# Custom CSS for Modern Styling & Severity Badges
# ==============================================================================

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .badge-live {
        background-color: #10B981;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-sim {
        background-color: #6366F1;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .alert-card-warning {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .alert-card-watch {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .alert-card-advisory {
        background-color: #EFF6FF;
        border-left: 5px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .disclaimer-box {
        background-color: #F3F4F6;
        border: 1px solid #E5E7EB;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 0.85rem;
        color: #374151;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# Sidebar Controls & User Inputs
# ==============================================================================

st.sidebar.image("https://img.icons8.com/clouds/200/sun.png", width=110)
st.sidebar.title("Configuration & Controls")

mode = st.sidebar.radio(
    "Data Source Mode",
    options=["Live API", "Virtual Simulation"],
    help="Select 'Live API' for real-time worldwide observations via Open-Meteo, or 'Virtual Simulation' for offline scenario testing."
)

use_simulation = (mode == "Virtual Simulation")
city_input = "Mangaluru"
scenario_id = "normal_weather"

if use_simulation:
    st.sidebar.info("💡 Offline Mode: Test extreme weather conditions and compound alert triggers without network access.")
    scenario_selection = st.sidebar.selectbox(
        "Choose Simulation Scenario",
        options=list(AVAILABLE_SCENARIOS.keys()),
        format_func=lambda x: AVAILABLE_SCENARIOS[x]
    )
    scenario_id = scenario_selection
else:
    city_input = st.sidebar.text_input(
        "Enter City Name",
        value="Mangaluru",
        help="Type any worldwide city name (e.g. Mangaluru, London, Tokyo, Delhi, New York)"
    )

# Configurable Alert Thresholds Expander
with st.sidebar.expander("⚙️ Alert Threshold Settings", expanded=False):
    t_temp = st.slider("High Temperature Threshold (°C)", min_value=30.0, max_value=50.0, value=40.0, step=0.5)
    t_hum = st.slider("High Humidity Threshold (%)", min_value=60.0, max_value=100.0, value=85.0, step=1.0)
    t_rain = st.slider("Rain Probability Threshold (%)", min_value=50.0, max_value=100.0, value=70.0, step=1.0)
    t_wind = st.slider("Wind Speed Threshold (km/h)", min_value=30.0, max_value=100.0, value=50.0, step=1.0)

custom_thresholds = AlertThresholds(
    high_temp_c=t_temp,
    high_humidity_pct=t_hum,
    high_rain_prob_pct=t_rain,
    high_wind_speed_kmh=t_wind
)

fetch_button = st.sidebar.button("🔄 Fetch & Analyze Weather", type="primary", use_container_width=True)

# Maintain state in session_state to avoid disappearing on minor interactions
if "weather_data" not in st.session_state:
    st.session_state["weather_data"] = None


# ==============================================================================
# Data Retrieval & Workflow Execution
# ==============================================================================

if fetch_button or st.session_state["weather_data"] is None:
    cleaned_city = city_input.strip() if city_input else "Mangaluru"
    with st.spinner(f"Retrieving and analyzing weather for {cleaned_city}..."):
        try:
            results = execute_weather_workflow(
                city_name=cleaned_city,
                use_simulation=use_simulation,
                scenario_id=scenario_id,
                thresholds=custom_thresholds,
                generate_charts=True,
                generate_reports=True
            )
            st.session_state["weather_data"] = results
        except CityNotFoundError as exc:
            st.error(f"❌ City Not Found: {exc}")
            st.session_state["weather_data"] = None
        except NetworkTimeoutError as exc:
            st.error(f"⏱️ Network Timeout: {exc}")
            st.info("Tip: Switch to Virtual Simulation in the sidebar to test offline.")
            st.session_state["weather_data"] = None
        except APIConnectionError as exc:
            st.error(f"🌐 Connection Failure: {exc}")
            st.info("Tip: Switch to Virtual Simulation in the sidebar to test offline.")
            st.session_state["weather_data"] = None
        except APIResponseError as exc:
            st.error(f"⚠️ Weather API Error: {exc}")
            st.session_state["weather_data"] = None
        except Exception as exc:
            st.error(f"⚠️ An unexpected error occurred: {exc}")
            st.session_state["weather_data"] = None

data = st.session_state.get("weather_data")


# ==============================================================================
# Dashboard Main Content Layout
# ==============================================================================

st.markdown('<div class="main-title">Weather Forecast & Alert Application</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Real-Time Meteorological Intelligence, Statistical Analytics, and Rule-Based Hazard Early Warning System</div>', unsafe_allow_html=True)

if data is not None:
    city = data["city"]
    country = data["country"]
    current = data["current"]
    is_sim = data["is_simulated"]
    badge_html = '<span class="badge-sim">SIMULATED DATA</span>' if is_sim else '<span class="badge-live">LIVE OBSERVATION</span>'

    # Current Status Subheader
    st.markdown(f"### Location: **{city}, {country}** &nbsp; {badge_html}", unsafe_allow_html=True)
    obs_time = str(current.get("timestamp", "Current Time"))
    st.caption(f"Observation Timestamp: **{obs_time}** | Weather Condition: **{current.get('weather_condition', 'N/A')}**")

    # 1. Current Weather KPI Metrics
    col1, col2, col3, col4 = st.columns(4)

    t_val = current.get("temperature_c")
    col1.metric("Temperature", f"{t_val:.1f} °C" if t_val is not None else "N/A", help="Ambient air temperature at 2m above ground")

    h_val = current.get("humidity_pct")
    col2.metric("Relative Humidity", f"{h_val:.0f} %" if h_val is not None else "N/A", help="Relative humidity percentage")

    w_val = current.get("wind_speed_kmh")
    col3.metric("Wind Speed", f"{w_val:.1f} km/h" if w_val is not None else "N/A", help="Sustained wind velocity at 10m")

    r_val = current.get("rain_probability_pct")
    col4.metric("Rain Probability", f"{r_val:.0f} %" if r_val is not None else "N/A", help="Probability of precipitation")

    st.divider()

    # 2. Weather Alert Monitoring Center
    alert_report = data.get("alert_report", {})
    has_alerts = alert_report.get("has_alerts", False)
    total_alerts = alert_report.get("total_alerts", 0)
    is_compound = alert_report.get("is_compound_risk", False)
    disclaimer = alert_report.get("disclaimer", "")

    st.subheader("🚨 Weather Alert Monitoring Center")

    if not has_alerts:
        st.success("✅ **STATUS: NORMAL** — All weather parameters are currently within normal thresholds. No active alerts.")
    else:
        compound_msg = " ⚡ **COMPOUND MULTI-HAZARD RISK DETECTED**" if is_compound else ""
        highest_sev = alert_report.get("highest_severity", "Advisory")

        if highest_sev == "Warning":
            st.error(f"🚨 **ACTIVE HAZARD WARNINGS ({total_alerts} Alert{'s' if total_alerts > 1 else ''} Detected)**{compound_msg}")
        elif highest_sev == "Watch":
            st.warning(f"⚠️ **ACTIVE WEATHER WATCH ({total_alerts} Alert{'s' if total_alerts > 1 else ''} Detected)**{compound_msg}")
        else:
            st.info(f"ℹ️ **ACTIVE WEATHER ADVISORY ({total_alerts} Alert{'s' if total_alerts > 1 else ''} Detected)**{compound_msg}")

        # Display Alert Cards
        all_alerts = alert_report.get("all_alerts", [])
        for a in all_alerts:
            sev = a.get("severity", "Advisory").lower()
            card_class = f"alert-card-{sev}"
            badge_color = "#EF4444" if sev == "warning" else ("#F59E0B" if sev == "watch" else "#3B82F6")

            st.markdown(f"""
            <div class="{card_class}">
                <span style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75rem;">
                    {a['severity'].upper()}
                </span>
                <strong style="margin-left: 8px; font-size: 0.95rem;">{a['alert_type']}</strong>
                <div style="font-size: 0.85rem; color: #374151; margin-top: 4px;">
                    {a['message']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Mandatory Safety Disclaimer
    st.markdown(f"""
    <div class="disclaimer-box">
        <strong>⚠️ Non-Official Informational Disclaimer:</strong><br>
        {disclaimer}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # 3. Forecast Statistical Analysis & Trends
    st.subheader("📊 Forecast Statistical Analysis & Trends")
    summary = data.get("forecast_summary", {})
    stats = summary.get("statistics", {})
    trend = summary.get("temperature_trend", {})

    st.write(f"**Executive Narrative**: {summary.get('overview', '')}")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    t_stats = stats.get("temperature", {})
    stat_col1.metric("Min / Max Temperature", f"{t_stats.get('min')}°C / {t_stats.get('max')}°C")

    stat_col2.metric("Temperature Trend", trend.get("trend", "Stable"), delta=f"{trend.get('delta_c', 0.0):+.1f} °C")

    p_stats = stats.get("precipitation", {})
    stat_col3.metric("Peak Rain Probability", f"{p_stats.get('max_probability', 0)} %")

    w_stats = stats.get("wind_speed", {})
    stat_col4.metric("Max Sustained Wind", f"{w_stats.get('max', 0)} km/h")

    st.divider()

    # 4. Forecast Visualizations & Tabbed Charts
    st.subheader("📈 Visual Meteorological Forecasts")
    charts = data.get("charts", {})

    tab_dash, tab_temp, tab_hum, tab_rain, tab_wind, tab_data = st.tabs([
        "Combined Dashboard",
        "Temperature",
        "Relative Humidity",
        "Precipitation",
        "Wind Speed",
        "Forecast Data Table"
    ])

    with tab_dash:
        if "dashboard" in charts and charts["dashboard"].exists():
            st.image(str(charts["dashboard"]), use_container_width=True)

    with tab_temp:
        if "temperature" in charts and charts["temperature"].exists():
            st.image(str(charts["temperature"]), use_container_width=True)

    with tab_hum:
        if "humidity" in charts and charts["humidity"].exists():
            st.image(str(charts["humidity"]), use_container_width=True)

    with tab_rain:
        if "precipitation" in charts and charts["precipitation"].exists():
            st.image(str(charts["precipitation"]), use_container_width=True)

    with tab_wind:
        if "wind" in charts and charts["wind"].exists():
            st.image(str(charts["wind"]), use_container_width=True)

    with tab_data:
        df_forecast = data.get("forecast_df")
        if df_forecast is not None and not df_forecast.empty:
            st.dataframe(df_forecast, use_container_width=True)

    st.divider()

    # 5. Report Downloads & Exports
    st.subheader("💾 Export & Download Reports")
    reports = data.get("reports", {})
    down_col1, down_col2 = st.columns(2)

    if "json_report" in reports and reports["json_report"].exists():
        with open(reports["json_report"], "r", encoding="utf-8") as f:
            json_str = f.read()
        down_col1.download_button(
            label="📄 Download Complete JSON Audit Report",
            data=json_str,
            file_name=reports["json_report"].name,
            mime="application/json",
            use_container_width=True
        )

    if "csv_report" in reports and reports["csv_report"].exists():
        with open(reports["csv_report"], "r", encoding="utf-8") as f:
            csv_str = f.read()
        down_col2.download_button(
            label="📊 Download Persistent CSV Weather History",
            data=csv_str,
            file_name="weather_reports.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    st.info("👈 Please enter a city or select a simulation scenario from the sidebar, then click 'Fetch & Analyze Weather'.")
