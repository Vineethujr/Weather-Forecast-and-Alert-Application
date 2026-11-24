"""
Forecast Statistical Analysis Module.
Computes statistical aggregates (Min, Max, Mean, Cumulative Precipitation),
evaluates chronological temperature trends (Warming, Cooling, Stable),
identifies peak meteorological intervals, and generates executive forecast summaries.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ForecastAnalysisError(Exception):
    """Raised when forecast statistical analysis encounters invalid or corrupted data."""
    pass


# ==============================================================================
# Statistical Calculations
# ==============================================================================

def _safe_metric_stats(series: Optional[pd.Series]) -> Dict[str, Optional[float]]:
    """
    Computes min, max, and mean for a numeric Pandas Series.
    Preserves missing values: returns None if series is missing or has all NaN values.
    Distinguishes genuine 0.0 from unavailable data.
    """
    if series is None or series.empty:
        return {"min": None, "max": None, "mean": None}

    valid_vals = series.dropna()
    if valid_vals.empty:
        return {"min": None, "max": None, "mean": None}

    return {
        "min": round(float(valid_vals.min()), 2),
        "max": round(float(valid_vals.max()), 2),
        "mean": round(float(valid_vals.mean()), 2),
    }


def calculate_forecast_statistics(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Calculates statistical summaries across all available forecast intervals.
    
    Args:
        df: Pandas DataFrame containing normalized forecast measurements.
        
    Returns:
        Structured dictionary with min/max/mean for temperature, humidity, wind,
        rain probability, cumulative precipitation, and data quality counts.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "total_intervals": 0,
            "temperature": {"min": None, "max": None, "mean": None},
            "humidity": {"min": None, "max": None, "mean": None},
            "wind_speed": {"min": None, "max": None, "mean": None, "max_gust": None},
            "precipitation": {
                "max_probability": None,
                "mean_probability": None,
                "cumulative_amount_mm": None,
            },
            "data_quality": {
                "total_intervals": 0,
                "missing_temperature_count": 0,
                "missing_humidity_count": 0,
                "missing_wind_count": 0,
                "missing_rain_prob_count": 0,
                "missing_precipitation_count": 0,
            }
        }

    total_rows = len(df)

    # Temperature stats
    temp_series = df.get("temperature_c")
    temp_stats = _safe_metric_stats(temp_series)

    # Humidity stats
    hum_series = df.get("humidity_pct")
    hum_stats = _safe_metric_stats(hum_series)

    # Wind stats
    wind_series = df.get("wind_speed_kmh")
    wind_stats = _safe_metric_stats(wind_series)
    
    # Wind gust handling (check for wind_gust_kmh if provided, else peak sustained wind)
    max_gust: Optional[float] = None
    if "wind_gust_kmh" in df.columns:
        gust_series = df["wind_gust_kmh"].dropna()
        if not gust_series.empty:
            max_gust = round(float(gust_series.max()), 2)
    elif wind_stats["max"] is not None:
        max_gust = wind_stats["max"]

    wind_stats["max_gust"] = max_gust

    # Precipitation stats
    rain_prob_series = df.get("rain_probability_pct")
    rain_prob_stats = _safe_metric_stats(rain_prob_series)

    precip_series = df.get("precipitation_mm")
    cumulative_precip: Optional[float] = None
    if precip_series is not None:
        valid_precip = precip_series.dropna()
        if not valid_precip.empty:
            cumulative_precip = round(float(valid_precip.sum()), 2)

    precip_stats = {
        "max_probability": rain_prob_stats["max"],
        "mean_probability": rain_prob_stats["mean"],
        "cumulative_amount_mm": cumulative_precip,
    }

    # Data Quality & Missing Value Audit
    data_quality = {
        "total_intervals": total_rows,
        "missing_temperature_count": int(temp_series.isna().sum()) if temp_series is not None else total_rows,
        "missing_humidity_count": int(hum_series.isna().sum()) if hum_series is not None else total_rows,
        "missing_wind_count": int(wind_series.isna().sum()) if wind_series is not None else total_rows,
        "missing_rain_prob_count": int(rain_prob_series.isna().sum()) if rain_prob_series is not None else total_rows,
        "missing_precipitation_count": int(precip_series.isna().sum()) if precip_series is not None else total_rows,
    }

    return {
        "total_intervals": total_rows,
        "temperature": temp_stats,
        "humidity": hum_stats,
        "wind_speed": wind_stats,
        "precipitation": precip_stats,
        "data_quality": data_quality,
    }


# ==============================================================================
# Temperature Trend Analysis
# ==============================================================================

def determine_temperature_trend(
    df: Optional[pd.DataFrame],
    tolerance_c: float = 1.5
) -> Dict[str, Any]:
    """
    Identifies whether upcoming temperatures exhibit a 'Warming', 'Cooling', or 'Stable' trend.
    
    Guarantees chronological sorting before calculation to avoid errors with out-of-order data.
    Uses a configurable tolerance band to prevent classifying minor ambient noise as a trend.
    
    Args:
        df: Pandas DataFrame with 'timestamp' and 'temperature_c' columns.
        tolerance_c: Temperature difference threshold (in °C) to qualify as warming/cooling.
        
    Returns:
        Dict containing trend classification ('Warming', 'Cooling', 'Stable', 'Undetermined'),
        delta_c, start_temp, end_temp, and tolerance used.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "trend": "Undetermined",
            "delta_c": None,
            "start_temperature_c": None,
            "end_temperature_c": None,
            "tolerance_c": tolerance_c,
            "reason": "Forecast DataFrame is empty or None."
        }

    if "temperature_c" not in df.columns:
        return {
            "trend": "Undetermined",
            "delta_c": None,
            "start_temperature_c": None,
            "end_temperature_c": None,
            "tolerance_c": tolerance_c,
            "reason": "Missing 'temperature_c' column."
        }

    # Sort chronologically by timestamp if timestamp column exists
    working_df = df.copy()
    if "timestamp" in working_df.columns:
        working_df["timestamp"] = pd.to_datetime(working_df["timestamp"])
        working_df = working_df.sort_values(by="timestamp").reset_index(drop=True)

    # Filter out missing temperature values
    valid_temps = working_df["temperature_c"].dropna()
    if len(valid_temps) < 2:
        return {
            "trend": "Undetermined",
            "delta_c": None,
            "start_temperature_c": float(valid_temps.iloc[0]) if len(valid_temps) == 1 else None,
            "end_temperature_c": None,
            "tolerance_c": tolerance_c,
            "reason": "Fewer than two valid temperature measurements available."
        }

    first_temp = float(valid_temps.iloc[0])
    last_temp = float(valid_temps.iloc[-1])
    delta_c = round(last_temp - first_temp, 2)

    if delta_c > tolerance_c:
        trend = "Warming"
    elif delta_c < -tolerance_c:
        trend = "Cooling"
    else:
        trend = "Stable"

    return {
        "trend": trend,
        "delta_c": delta_c,
        "start_temperature_c": round(first_temp, 2),
        "end_temperature_c": round(last_temp, 2),
        "tolerance_c": tolerance_c,
        "reason": f"Net temperature change is {delta_c:+.2f}°C over the forecast horizon."
    }


# ==============================================================================
# Peak & High-Impact Interval Detection
# ==============================================================================

def identify_peak_intervals(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Identifies chronological intervals where peak weather phenomena occur
    (highest temperature, lowest temperature, maximum rain probability, peak wind speed).
    
    Args:
        df: Pandas DataFrame of forecast intervals.
        
    Returns:
        Dict mapping peak criteria to interval details (timestamp, value, condition).
    """
    peaks: Dict[str, Any] = {
        "peak_temperature": None,
        "lowest_temperature": None,
        "peak_rain_probability": None,
        "peak_wind_speed": None,
    }

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return peaks

    def _extract_row_summary(row: pd.Series, val_key: str) -> Dict[str, Any]:
        ts = row.get("timestamp")
        ts_str = str(ts) if pd.notna(ts) else "Unknown Time"
        val = row.get(val_key)
        val_clean = round(float(val), 2) if pd.notna(val) else None
        return {
            "timestamp": ts_str,
            "value": val_clean,
            "condition": str(row.get("weather_condition", "Unknown")),
        }

    # 1. Peak Temperature
    if "temperature_c" in df.columns:
        valid_t = df.dropna(subset=["temperature_c"])
        if not valid_t.empty:
            max_t_idx = valid_t["temperature_c"].idxmax()
            peaks["peak_temperature"] = _extract_row_summary(valid_t.loc[max_t_idx], "temperature_c")
            min_t_idx = valid_t["temperature_c"].idxmin()
            peaks["lowest_temperature"] = _extract_row_summary(valid_t.loc[min_t_idx], "temperature_c")

    # 2. Peak Rain Probability
    if "rain_probability_pct" in df.columns:
        valid_r = df.dropna(subset=["rain_probability_pct"])
        if not valid_r.empty:
            max_r_idx = valid_r["rain_probability_pct"].idxmax()
            peaks["peak_rain_probability"] = _extract_row_summary(valid_r.loc[max_r_idx], "rain_probability_pct")

    # 3. Peak Wind Speed
    if "wind_speed_kmh" in df.columns:
        valid_w = df.dropna(subset=["wind_speed_kmh"])
        if not valid_w.empty:
            max_w_idx = valid_w["wind_speed_kmh"].idxmax()
            peaks["peak_wind_speed"] = _extract_row_summary(valid_w.loc[max_w_idx], "wind_speed_kmh")

    return peaks


# ==============================================================================
# Master Forecast Summary Generator
# ==============================================================================

def generate_forecast_summary(
    df: Optional[pd.DataFrame],
    metadata: Optional[Dict[str, Any]] = None,
    trend_tolerance_c: float = 1.5
) -> Dict[str, Any]:
    """
    Master pipeline function that performs end-to-end forecast statistical analysis.
    
    Generates:
    - Statistical summaries (Min, Max, Mean, Totals)
    - Chronological temperature trend (Warming, Cooling, Stable)
    - Key peak meteorological intervals
    - Human-readable executive overview
    - Data quality and missing data audit
    
    Args:
        df: Pandas DataFrame containing forecast intervals.
        metadata: Optional top-level metadata from data processing (city, data_source, etc.).
        trend_tolerance_c: Temperature variation tolerance in °C.
        
    Returns:
        Comprehensive statistical summary dictionary.
    """
    if metadata is None:
        metadata = {}

    data_source = metadata.get("data_source", "UNKNOWN")
    is_simulated = bool(metadata.get("is_simulated", data_source == "SIMULATED"))
    city = metadata.get("city", "Unknown City")
    country = metadata.get("country", "Unknown Country")

    # 1. Compute statistical aggregates
    stats = calculate_forecast_statistics(df)

    # 2. Compute temperature trend
    trend_info = determine_temperature_trend(df, tolerance_c=trend_tolerance_c)

    # 3. Identify peak intervals
    peaks = identify_peak_intervals(df)

    # 4. Synthesize human-readable executive overview
    t_min = stats["temperature"]["min"]
    t_max = stats["temperature"]["max"]
    t_mean = stats["temperature"]["mean"]
    max_rain = stats["precipitation"]["max_probability"]
    cum_rain = stats["precipitation"]["cumulative_amount_mm"]
    max_wind = stats["wind_speed"]["max"]
    trend_name = trend_info["trend"]

    if stats["total_intervals"] == 0:
        overview_text = f"No forecast intervals available for {city}, {country}."
    else:
        overview_parts = [
            f"Forecast for {city}, {country} covering {stats['total_intervals']} intervals."
        ]
        if t_min is not None and t_max is not None and t_mean is not None:
            overview_parts.append(
                f"Temperatures range from {t_min}°C to {t_max}°C (average {t_mean}°C) exhibiting a {trend_name} trend."
            )
        if max_rain is not None:
            rain_note = f"Peak rainfall probability is {max_rain}%"
            if cum_rain is not None and cum_rain > 0:
                rain_note += f" with {cum_rain} mm expected accumulation."
            else:
                rain_note += "."
            overview_parts.append(rain_note)
        if max_wind is not None:
            overview_parts.append(f"Maximum wind speeds reach {max_wind} km/h.")

        overview_text = " ".join(overview_parts)

    return {
        "data_source": data_source,
        "is_simulated": is_simulated,
        "city": city,
        "country": country,
        "overview": overview_text,
        "statistics": stats,
        "temperature_trend": trend_info,
        "peak_intervals": peaks,
        "data_quality": stats["data_quality"],
    }
