"""
Weather Visualization Engine.
Generates professional, publication-ready weather forecast charts using Matplotlib.
Includes individual time-series charts for temperature, humidity, precipitation,
wind speed, and a unified 4-panel multi-metric weather dashboard.
Enforces headless rendering, explicit threshold overlays, simulation watermarks,
clean timestamp formatting, and memory leak prevention via figure lifecycle management.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
# Enforce headless Agg backend for robust server, terminal, and testing execution
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base output directory
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


# ==============================================================================
# Helper Formatting Utilities
# ==============================================================================

def _get_output_dir(custom_dir: Optional[Path] = None) -> Path:
    """Ensures output directory exists and returns resolved Path."""
    out_dir = custom_dir if custom_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_city_slug(city: str) -> str:
    """Converts a city name into a filesystem-safe slug (e.g. 'Kochi Coastal' -> 'kochi_coastal')."""
    return "".join(c if c.isalnum() else "_" for c in city.strip().lower()).strip("_")


def _format_chart_title(metric: str, city: str, is_simulated: bool) -> str:
    """Formats a standardized chart title with explicit simulation indicators."""
    sim_badge = "[SIMULATED DATA]" if is_simulated else "[LIVE]"
    return f"{city} - {metric} Forecast {sim_badge}"


def _format_time_labels(timestamps: pd.Series) -> List[str]:
    """Formats datetime series into concise readable strings for x-axis ticks."""
    formatted: List[str] = []
    for ts in timestamps:
        if pd.isna(ts):
            formatted.append("N/A")
            continue
        try:
            ts_dt = pd.to_datetime(ts)
            formatted.append(ts_dt.strftime("%b %d, %H:%M"))
        except Exception:
            formatted.append(str(ts))
    return formatted


def _render_empty_chart(ax: plt.Axes, message: str = "No Forecast Data Available") -> None:
    """Renders a clean placeholder message on an empty or invalid chart axis."""
    ax.text(
        0.5, 0.5, message,
        horizontalalignment="center",
        verticalalignment="center",
        transform=ax.transAxes,
        fontsize=12,
        color="gray",
        style="italic"
    )
    ax.set_xticks([])
    ax.set_yticks([])


# ==============================================================================
# 1. Temperature Forecast Chart
# ==============================================================================

def plot_temperature_forecast(
    df: Optional[pd.DataFrame],
    city: str = "Unknown City",
    is_simulated: bool = False,
    threshold_c: float = 40.0,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Renders a time-series line chart for forecast temperatures with threshold reference line.
    """
    out_path = _get_output_dir(output_dir)
    slug = _safe_city_slug(city)
    file_name = filename or f"{slug}_temperature_forecast.png"
    target_file = out_path / file_name

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "temperature_c" not in df.columns:
        _render_empty_chart(ax, "No temperature data available")
    else:
        valid_df = df.dropna(subset=["timestamp"]).copy()
        x_labels = _format_time_labels(valid_df["timestamp"])
        x_indices = range(len(valid_df))
        temps = valid_df["temperature_c"]

        # Plot temperature trend
        ax.plot(
            x_indices, temps,
            color="#E65100", linewidth=2.2, marker="o", markersize=6,
            label="Forecast Temperature (°C)"
        )

        # Plot threshold line
        ax.axhline(
            y=threshold_c, color="#D32F2F", linestyle="--", linewidth=1.8,
            label=f"Alert Threshold ({threshold_c:.1f}°C)"
        )

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Temperature (°C)", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="best", frameon=True, facecolor="#FAFAFA")

        # Value annotations
        for idx, temp in enumerate(temps):
            if pd.notna(temp):
                ax.annotate(
                    f"{temp:.1f}°",
                    (idx, temp),
                    textcoords="offset points",
                    xytext=(0, 7),
                    ha="center",
                    fontsize=8,
                    fontweight="bold"
                )

    ax.set_title(_format_chart_title("Temperature", city, is_simulated), fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    fig.savefig(target_file, dpi=120)
    plt.close(fig)

    logger.info(f"Saved temperature chart to {target_file}")
    return target_file


# ==============================================================================
# 2. Humidity Forecast Chart
# ==============================================================================

def plot_humidity_forecast(
    df: Optional[pd.DataFrame],
    city: str = "Unknown City",
    is_simulated: bool = False,
    threshold_pct: float = 85.0,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Renders a time-series line chart for relative humidity with threshold reference line.
    """
    out_path = _get_output_dir(output_dir)
    slug = _safe_city_slug(city)
    file_name = filename or f"{slug}_humidity_forecast.png"
    target_file = out_path / file_name

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "humidity_pct" not in df.columns:
        _render_empty_chart(ax, "No humidity data available")
    else:
        valid_df = df.dropna(subset=["timestamp"]).copy()
        x_labels = _format_time_labels(valid_df["timestamp"])
        x_indices = range(len(valid_df))
        humidity = valid_df["humidity_pct"]

        # Plot humidity trend
        ax.plot(
            x_indices, humidity,
            color="#0288D1", linewidth=2.2, marker="s", markersize=6,
            label="Relative Humidity (%)"
        )

        # Plot threshold line
        ax.axhline(
            y=threshold_pct, color="#D32F2F", linestyle="--", linewidth=1.8,
            label=f"Alert Threshold ({threshold_pct:.1f}%)"
        )

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Relative Humidity (%)", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="best", frameon=True, facecolor="#FAFAFA")

        # Value annotations
        for idx, hum in enumerate(humidity):
            if pd.notna(hum):
                ax.annotate(
                    f"{hum:.0f}%",
                    (idx, hum),
                    textcoords="offset points",
                    xytext=(0, 7),
                    ha="center",
                    fontsize=8
                )

    ax.set_title(_format_chart_title("Relative Humidity", city, is_simulated), fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    fig.savefig(target_file, dpi=120)
    plt.close(fig)

    logger.info(f"Saved humidity chart to {target_file}")
    return target_file


# ==============================================================================
# 3. Precipitation Probability Chart
# ==============================================================================

def plot_precipitation_forecast(
    df: Optional[pd.DataFrame],
    city: str = "Unknown City",
    is_simulated: bool = False,
    threshold_pct: float = 70.0,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Renders a bar chart for precipitation probability with alert threshold overlay.
    """
    out_path = _get_output_dir(output_dir)
    slug = _safe_city_slug(city)
    file_name = filename or f"{slug}_precipitation_forecast.png"
    target_file = out_path / file_name

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "rain_probability_pct" not in df.columns:
        _render_empty_chart(ax, "No precipitation probability data available")
    else:
        valid_df = df.dropna(subset=["timestamp"]).copy()
        x_labels = _format_time_labels(valid_df["timestamp"])
        x_indices = np.arange(len(valid_df))
        rain_prob = valid_df["rain_probability_pct"]

        # Color bars according to whether they breach the threshold
        bar_colors = [
            "#D32F2F" if (pd.notna(p) and p > threshold_pct) else "#1976D2"
            for p in rain_prob
        ]

        bars = ax.bar(
            x_indices, rain_prob,
            color=bar_colors, width=0.55, edgecolor="#0D47A1", alpha=0.85,
            label="Rain Probability (%)"
        )

        # Plot threshold line
        ax.axhline(
            y=threshold_pct, color="#D32F2F", linestyle="--", linewidth=1.8,
            label=f"Alert Threshold ({threshold_pct:.1f}%)"
        )

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Probability of Precipitation (%)", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.grid(True, axis="y", linestyle=":", alpha=0.6)
        ax.legend(loc="upper right", frameon=True, facecolor="#FAFAFA")

        # Value annotations atop bars
        for bar in bars:
            height = bar.get_height()
            if pd.notna(height) and height > 0:
                ax.annotate(
                    f"{height:.0f}%",
                    (bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold"
                )

    ax.set_title(_format_chart_title("Precipitation Probability", city, is_simulated), fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    fig.savefig(target_file, dpi=120)
    plt.close(fig)

    logger.info(f"Saved precipitation chart to {target_file}")
    return target_file


# ==============================================================================
# 4. Wind Speed & Gusts Chart
# ==============================================================================

def plot_wind_forecast(
    df: Optional[pd.DataFrame],
    city: str = "Unknown City",
    is_simulated: bool = False,
    threshold_kmh: float = 50.0,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Renders a line chart for sustained wind speeds and gusts with threshold reference line.
    """
    out_path = _get_output_dir(output_dir)
    slug = _safe_city_slug(city)
    file_name = filename or f"{slug}_wind_forecast.png"
    target_file = out_path / file_name

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "wind_speed_kmh" not in df.columns:
        _render_empty_chart(ax, "No wind speed data available")
    else:
        valid_df = df.dropna(subset=["timestamp"]).copy()
        x_labels = _format_time_labels(valid_df["timestamp"])
        x_indices = range(len(valid_df))
        wind_speed = valid_df["wind_speed_kmh"]

        # Plot sustained wind speed
        ax.plot(
            x_indices, wind_speed,
            color="#00796B", linewidth=2.2, marker="^", markersize=6,
            label="Sustained Wind Speed (km/h)"
        )

        # Plot wind gusts if available
        if "wind_gust_kmh" in valid_df.columns:
            gusts = valid_df["wind_gust_kmh"]
            if gusts.notna().any():
                ax.plot(
                    x_indices, gusts,
                    color="#FF8F00", linewidth=1.8, linestyle=":", marker="x", markersize=6,
                    label="Wind Gusts (km/h)"
                )

        # Plot threshold line
        ax.axhline(
            y=threshold_kmh, color="#D32F2F", linestyle="--", linewidth=1.8,
            label=f"Alert Threshold ({threshold_kmh:.1f} km/h)"
        )

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Wind Speed (km/h)", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="best", frameon=True, facecolor="#FAFAFA")

        # Value annotations
        for idx, wind in enumerate(wind_speed):
            if pd.notna(wind):
                ax.annotate(
                    f"{wind:.1f}",
                    (idx, wind),
                    textcoords="offset points",
                    xytext=(0, 7),
                    ha="center",
                    fontsize=8
                )

    ax.set_title(_format_chart_title("Wind Speed", city, is_simulated), fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    fig.savefig(target_file, dpi=120)
    plt.close(fig)

    logger.info(f"Saved wind chart to {target_file}")
    return target_file


# ==============================================================================
# 5. Combined Multi-Panel Weather Dashboard Chart
# ==============================================================================

def plot_combined_dashboard(
    df: Optional[pd.DataFrame],
    city: str = "Unknown City",
    is_simulated: bool = False,
    threshold_temp_c: float = 40.0,
    threshold_humidity_pct: float = 85.0,
    threshold_rain_prob_pct: float = 70.0,
    threshold_wind_kmh: float = 50.0,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Renders a unified 4-panel meteorological dashboard (2x2 grid).
    Guarantees that each metric is plotted on its own independent scale and unit.
    """
    out_path = _get_output_dir(output_dir)
    slug = _safe_city_slug(city)
    file_name = filename or f"{slug}_weather_dashboard.png"
    target_file = out_path / file_name

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 9), dpi=120)

    has_data = df is not None and isinstance(df, pd.DataFrame) and not df.empty and "timestamp" in df.columns

    if not has_data:
        for ax in (ax1, ax2, ax3, ax4):
            _render_empty_chart(ax, "No forecast data available")
    else:
        valid_df = df.dropna(subset=["timestamp"]).copy()
        x_labels = _format_time_labels(valid_df["timestamp"])
        x_indices = range(len(valid_df))

        # Panel 1: Temperature
        if "temperature_c" in valid_df.columns:
            temps = valid_df["temperature_c"]
            ax1.plot(x_indices, temps, color="#E65100", linewidth=2.0, marker="o", label="Temperature (°C)")
            ax1.axhline(threshold_temp_c, color="#D32F2F", linestyle="--", linewidth=1.5, label=f"Alert ({threshold_temp_c}°C)")
            ax1.set_ylabel("Temperature (°C)", fontweight="bold")
            ax1.set_title("Temperature Forecast", fontsize=11, fontweight="bold")
            ax1.set_xticks(x_indices)
            ax1.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
            ax1.grid(True, linestyle=":", alpha=0.6)
            ax1.legend(loc="best", fontsize=8)

        # Panel 2: Relative Humidity
        if "humidity_pct" in valid_df.columns:
            hums = valid_df["humidity_pct"]
            ax2.plot(x_indices, hums, color="#0288D1", linewidth=2.0, marker="s", label="Humidity (%)")
            ax2.axhline(threshold_humidity_pct, color="#D32F2F", linestyle="--", linewidth=1.5, label=f"Alert ({threshold_humidity_pct}%)")
            ax2.set_ylabel("Humidity (%)", fontweight="bold")
            ax2.set_ylim(0, 105)
            ax2.set_title("Relative Humidity Forecast", fontsize=11, fontweight="bold")
            ax2.set_xticks(x_indices)
            ax2.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
            ax2.grid(True, linestyle=":", alpha=0.6)
            ax2.legend(loc="best", fontsize=8)

        # Panel 3: Precipitation Probability
        if "rain_probability_pct" in valid_df.columns:
            probs = valid_df["rain_probability_pct"]
            bar_colors = ["#D32F2F" if (pd.notna(p) and p > threshold_rain_prob_pct) else "#1976D2" for p in probs]
            ax3.bar(x_indices, probs, color=bar_colors, width=0.55, label="Rain Prob (%)")
            ax3.axhline(threshold_rain_prob_pct, color="#D32F2F", linestyle="--", linewidth=1.5, label=f"Alert ({threshold_rain_prob_pct}%)")
            ax3.set_ylabel("Probability (%)", fontweight="bold")
            ax3.set_ylim(0, 105)
            ax3.set_title("Precipitation Probability", fontsize=11, fontweight="bold")
            ax3.set_xticks(x_indices)
            ax3.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
            ax3.grid(True, axis="y", linestyle=":", alpha=0.6)
            ax3.legend(loc="best", fontsize=8)

        # Panel 4: Wind Speed
        if "wind_speed_kmh" in valid_df.columns:
            winds = valid_df["wind_speed_kmh"]
            ax4.plot(x_indices, winds, color="#00796B", linewidth=2.0, marker="^", label="Wind Speed (km/h)")
            ax4.axhline(threshold_wind_kmh, color="#D32F2F", linestyle="--", linewidth=1.5, label=f"Alert ({threshold_wind_kmh} km/h)")
            ax4.set_ylabel("Wind Speed (km/h)", fontweight="bold")
            ax4.set_title("Wind Speed Forecast", fontsize=11, fontweight="bold")
            ax4.set_xticks(x_indices)
            ax4.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
            ax4.grid(True, linestyle=":", alpha=0.6)
            ax4.legend(loc="best", fontsize=8)

    # Master title
    sim_badge = "[SIMULATED DATA]" if is_simulated else "[LIVE OBSERVATION]"
    fig.suptitle(f"{city} - Comprehensive Weather Forecast Dashboard {sim_badge}", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(target_file, dpi=120)
    plt.close(fig)

    logger.info(f"Saved combined dashboard chart to {target_file}")
    return target_file


# ==============================================================================
# Master Chart Suite Generator
# ==============================================================================

def generate_all_forecast_charts(
    df: Optional[pd.DataFrame],
    metadata: Optional[Dict[str, Any]] = None,
    thresholds: Optional[Any] = None,
    output_dir: Optional[Path] = None
) -> Dict[str, Path]:
    """
    Batch generates the full suite of 5 weather charts (Temperature, Humidity,
    Precipitation, Wind, and Combined Dashboard).
    
    Args:
        df: Pandas DataFrame of forecast intervals.
        metadata: Top-level metadata dictionary (city, data_source, is_simulated).
        thresholds: AlertThresholds configuration instance.
        output_dir: Optional custom directory to save images.
        
    Returns:
        Dict mapping chart keys to their saved Path locations.
    """
    if metadata is None:
        metadata = {}

    city = metadata.get("city", "Unknown City")
    is_simulated = bool(metadata.get("is_simulated", False))

    # Fallback threshold values
    t_temp = getattr(thresholds, "high_temp_c", 40.0)
    t_hum = getattr(thresholds, "high_humidity_pct", 85.0)
    t_rain = getattr(thresholds, "high_rain_prob_pct", 70.0)
    t_wind = getattr(thresholds, "high_wind_speed_kmh", 50.0)

    slug = _safe_city_slug(city)

    return {
        "temperature": plot_temperature_forecast(
            df, city=city, is_simulated=is_simulated, threshold_c=t_temp,
            output_dir=output_dir, filename=f"{slug}_temperature_forecast.png"
        ),
        "humidity": plot_humidity_forecast(
            df, city=city, is_simulated=is_simulated, threshold_pct=t_hum,
            output_dir=output_dir, filename=f"{slug}_humidity_forecast.png"
        ),
        "precipitation": plot_precipitation_forecast(
            df, city=city, is_simulated=is_simulated, threshold_pct=t_rain,
            output_dir=output_dir, filename=f"{slug}_precipitation_forecast.png"
        ),
        "wind": plot_wind_forecast(
            df, city=city, is_simulated=is_simulated, threshold_kmh=t_wind,
            output_dir=output_dir, filename=f"{slug}_wind_forecast.png"
        ),
        "dashboard": plot_combined_dashboard(
            df, city=city, is_simulated=is_simulated,
            threshold_temp_c=t_temp, threshold_humidity_pct=t_hum,
            threshold_rain_prob_pct=t_rain, threshold_wind_kmh=t_wind,
            output_dir=output_dir, filename=f"{slug}_weather_dashboard.png"
        ),
    }
