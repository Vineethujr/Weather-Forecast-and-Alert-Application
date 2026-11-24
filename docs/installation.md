# Installation & Setup Guide

This guide provides beginner-friendly, step-by-step instructions for installing and running the **Weather Forecast & Alert Application** on Windows, macOS, and Linux.

---

## A. Prerequisites & Python Installation

### 1. Downloading Python
- Visit the official Python downloads page: [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Download a stable release: **Python 3.10, 3.11, or 3.12**.
- **Important for Windows Users**: During installation, check the box that says:
  > **[x] Add Python to PATH** (or **Add python.exe to PATH**)
  This ensures Python and pip can be run directly from any terminal.

### 2. Verifying Installation
Open your terminal (PowerShell, Command Prompt, or Bash) and execute:
```bash
python --version
```
*(On macOS/Linux, if `python` refers to an older version, run `python3 --version`)*

Expected output:
```text
Python 3.11.x (or compatible stable 3.10+)
```

Verify that `pip` is available:
```bash
pip --version
```

---

## B. Project Setup in Visual Studio Code (VS Code)

1. Open **VS Code**.
2. Click **File -> Open Folder...** (or press `Ctrl + K, Ctrl + O`).
3. Select the `Weather Forecast & Alert Application` directory.
4. Open the integrated terminal in VS Code:
   - Shortcut: ``Ctrl + ` `` (backtick) or go to menu **Terminal -> New Terminal**.

---

## C. Creating and Activating a Virtual Environment

### Why use a Virtual Environment (`.venv`)?
A virtual environment isolates project dependencies, preventing version conflicts with other projects on your computer.

### Windows (PowerShell or Command Prompt):
```powershell
# 1. Create the virtual environment folder named .venv
python -m venv .venv

# 2. Activate the virtual environment
.venv\Scripts\activate
```
*Note: If PowerShell displays a `Script Execution Policy` restriction, run:  
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` in that session, then re-run the activation script.*

### macOS / Linux (Terminal / Bash / Zsh):
```bash
# 1. Create the virtual environment
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate
```

When activated, your terminal prompt will display `(.venv)` at the beginning:
```text
(.venv) PS C:\Users\...\Weather Forecast & Alert Application>
```

---

## D. Library Installation

With your virtual environment activated, install all dependencies:
```bash
pip install -r requirements.txt
```

### Purpose of Dependencies:
- **`requests`**: Handles HTTP networking and REST API integration with Open-Meteo.
- **`pandas`**: Tabular data manipulation, time-series parsing, and summary statistics.
- **`numpy`**: High-performance numerical calculations and missing-value (`NaN`) management.
- **`matplotlib`**: Headless generation of time-series plots and multi-panel dashboards.
- **`python-dotenv`**: Securely loads environment variables from `.env` into `os.environ`.
- **`streamlit`**: Powers the interactive web dashboard with zero HTML/CSS overhead.
- **`pytest`**: Automated unit and integration test framework.

---

## E. Environment Variables Configuration

The project includes `.env.example` as a template.

1. Create your local `.env` file:
   - **Windows**:
     ```powershell
     copy .env.example .env
     ```
   - **macOS/Linux**:
     ```bash
     cp .env.example .env
     ```
2. Inspect or modify `.env` as needed:
   - `WEATHER_PROVIDER=open-meteo`: Default free public API requiring **no API key**.
   - `DEFAULT_CITY=Mangaluru`
   - Configurable alert threshold values:
     ```ini
     THRESHOLD_HIGH_TEMP_C=40.0
     THRESHOLD_HIGH_HUMIDITY_PCT=85.0
     THRESHOLD_HIGH_RAIN_PROB_PCT=70.0
     THRESHOLD_HIGH_WIND_SPEED_KMH=50.0
     ```

---

## F. Running the Application

### 1. Interactive Command-Line Interface (CLI):
```bash
# Interactive menu:
python main.py

# Direct live search:
python main.py --city Mangaluru

# Direct offline simulation:
python main.py --simulation compound_risks
```

### 2. Streamlit Web Dashboard:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to view the interactive dashboard.

### 3. Running Automated Tests:
```bash
pytest tests/ -v
```

---

## G. GitHub Security & Repository Hygiene

1. **Keep Secrets Private**: Never commit `.env` or personal credentials to Git.
2. **Verify `.gitignore`**: The `.gitignore` file excludes `.env`, `.venv/`, `__pycache__/`, `outputs/*`, and dynamic reports while keeping `.gitkeep` placeholders.
3. **Check Status Before Committing**:
   ```bash
   git status
   ```
   Ensure `.env` never appears under "Untracked files" or "Changes to be committed".
