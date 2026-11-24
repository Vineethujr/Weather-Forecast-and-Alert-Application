# Project Architecture & Modular Design

## 1. Overview
The **Weather Forecast & Alert Application** is built around the architectural principle of **Separation of Concerns (SoC)** and the **Orchestration Service Pattern**. 

By decoupling external API integration, data cleaning, statistical analysis, alert rule evaluation, data visualization, and reporting, the system guarantees that:
- Changes to third-party weather APIs do not break data analysis or the UI.
- Offline simulation fixtures work through the identical analytical pipeline as live data.
- Neither the Command-Line Interface (`main.py`) nor the Streamlit Dashboard (`app.py`) contains business logic.

---

## 2. Directory & Module Responsibilities

| Directory / File | Responsibility | Architectural Role |
|---|---|---|
| `src/weather_api.py` | Geocoding city names and fetching live Open-Meteo REST API data or offline simulation fixtures. | External I/O & Networking Layer |
| `src/data_processing.py` | Ingests raw JSON payloads, parses ISO 8601 timestamps, validates physical measurement bounds, and constructs clean Pandas DataFrames without coercing missing values to zero. | Data Transformation & Normalization Layer |
| `src/forecast_analysis.py` | Computes statistical summaries (Min, Max, Mean, Cumulative Precipitation), evaluates temperature trends (Warming, Cooling, Stable), and detects peak intervals. | Pure Business Analytics Layer |
| `src/alert_system.py` | Evaluates configurable weather thresholds, classifies informational severities (Advisory, Watch, Warning), detects compound risks, suppresses duplicates, and enforces non-official disclaimers. | Rule Evaluation Engine |
| `src/visualization.py` | Headless Matplotlib plotting engine generating publication-ready charts (Temperature, Humidity, Rain Probability, Wind, and 4-Panel Dashboard) with memory leak prevention. | Visualization Layer |
| `src/report_generator.py` | Appends observations to `reports/weather_reports.csv` and exports standalone atomic JSON audit reports with sanitized filenames. | Persistence & Archival Layer |
| `src/weather_service.py` | Central coordinator orchestrating the end-to-end pipeline (`execute_weather_workflow`) for both the CLI and Streamlit interfaces. | Orchestration Service Layer |
| `main.py` | Interactive terminal CLI supporting menu navigation, direct city searches, offline simulation flags, formatted ASCII tables, and alert monitors. | Presentation Layer (CLI) |
| `app.py` | Streamlit interactive web dashboard with KPI metric cards, alert banners, tabbed charts, real-time threshold sliders, and one-click report downloads. | Presentation Layer (Web) |
| `data/` | Offline simulation fixtures (`sample_weather.json`, `sample_forecast.json`) covering 6 distinct meteorological conditions. | Test Data Fixtures |
| `outputs/` | Destination folder for dynamically generated Matplotlib PNG charts. | Generated Visual Artifacts |
| `reports/` | Destination folder for persistent CSV logs and atomic JSON audit reports. | Generated Data Artifacts |
| `images/` | Static screenshot assets and chart previews for GitHub documentation. | Repository Documentation Assets |
| `tests/` | 89 automated unit and integration tests covering all modules using Pytest and mocks. | Automated Verification Suite |

---

## 3. End-to-End Data Flow Architecture

```
                       USER INTERACTION
              +---------------+---------------+
              |                               |
              v                               v
     Terminal CLI (main.py)          Streamlit App (app.py)
              |                               |
              +---------------+---------------+
                              |
                              v
                  src/weather_service.py
               (execute_weather_workflow)
                              |
      +-----------------------+-----------------------+
      |                                               |
      v                                               v
[Mode: LIVE API]                             [Mode: SIMULATION]
src/weather_api.py (Requests)            data/sample_weather.json
Open-Meteo REST API                      Offline Synthetic Fixtures
      |                                               |
      +-----------------------+-----------------------+
                              |
                              v
                   src/data_processing.py
             (JSON Parsing, Range Validation,
              Pandas DataFrame Normalization)
                              |
      +-----------------------+-----------------------+
      |                                               |
      v                                               v
src/forecast_analysis.py                    src/alert_system.py
(Min, Max, Avg, Trends,                     (Configurable Thresholds,
 Peak Intervals)                             Compound Risk Detection)
      |                                               |
      +-----------------------+-----------------------+
                              |
      +-----------------------+-----------------------+
      |                                               |
      v                                               v
src/visualization.py                       src/report_generator.py
(Matplotlib Headless Plots,                 (Persistent CSV Append,
 4-Panel Dashboard PNG)                      Atomic JSON Export)
      |                                               |
      +-----------------------+-----------------------+
                              |
                              v
                    RETURNED TO UI LAYER
           (Rendered in Terminal or Streamlit Web)
```
