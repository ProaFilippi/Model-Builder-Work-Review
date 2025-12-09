# Anaplan Log to Workhours Report

Python utility that turns Anaplan model history logs into a developer work-time report. It groups activity into sessions based on inactivity, summarizes hours per developer, and can export CSV or Excel dashboards.

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

The CLI prints what it finds, how many sessions were detected, and where exports are written.

## Notes
- Raw logs and generated reports (`.txt`, `.csv`, `.xlsx`, `Logs/`) are ignored by git to keep the repo clean—keep your data locally or rename the ignore rules if you need to commit samples.
