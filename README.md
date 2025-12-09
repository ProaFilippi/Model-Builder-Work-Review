# Anaplan Log to Workhours Report

Python utility and Streamlit web app that turns Anaplan model history logs into a developer work-time report. It groups activity into sessions based on inactivity, summarizes hours per developer, and can export CSV or Excel dashboards.

## 🌐 Web Application

Access the interactive Streamlit app for easy file uploads and visual analysis.

### Local Usage
```bash
streamlit run app.py
```

### Deploy to Render.com
1. Push this repository to GitHub
2. Go to [Render.com](https://render.com) → New Web Service
3. Connect your GitHub repository
4. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
5. Deploy!

## 💻 Command Line Tool

## Inputs
- Expects tab-separated history exports with columns such as `Date/Time (UTC)` and `User`.
- If no files are passed, it automatically scans the `Logs/` folder for `.txt` or `.csv` files.

## Setup
1) Install Python 3.10+.
2) Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
- Basic run using the default `Logs/` directory:
  ```bash
  python analyze_work_time.py
  ```
- Provide explicit files and tweak inactivity (minutes between sessions):
  ```bash
  python analyze_work_time.py Logs/CMC\ Datahub\ History\ Oct\ 26\ to\ Dec\ 8\ 2025.txt -i 45
  ```
- Useful flags:
  - `-o OUTPUT` save the text report to a file
  - `--csv` export chunk and summary CSVs (named after the first input file)
  - `--excel FILE.xlsx` export a multi-tab Excel report
  - `--summary` show only the per-developer summary
  - `--min-hours X` filter out developers with total hours below X (e.g., `--min-hours 1.0`)

The CLI prints what it finds, how many sessions were detected, and where exports are written.

## Notes
- Raw logs and generated reports (`.txt`, `.csv`, `.xlsx`, `Logs/`) are ignored by git to keep the repo clean—keep your data locally or rename the ignore rules if you need to commit samples.
