# AI-Powered Employee Burnout Detection and Well-being Monitoring System

A complete final-year project prototype for detecting employee burnout risk from work patterns, sentiment, and wellness indicators.

## What Is Included

- Interactive HR dashboard with team risk analytics
- Employee wellness dashboard with personal trend and recommendations
- Burnout prediction form with sentiment analysis
- Pure Python prediction engine and optional API server
- Sample employee dataset
- SQL database schema
- Project report and UML diagrams

## Run The Web App

Open this file in a browser:

```text
index.html
```

The app works without installing packages because the sample data and prediction model are bundled locally.

## Optional API Server

If you want to run the app through a local Python server:

```powershell
python backend\api_server.py
```

Then open:

```text
http://localhost:8001
```

API endpoints:

- `GET /api/health`
- `GET /api/employees`
- `POST /api/predict`

Example request:

```json
{
  "work_hours": 9.5,
  "overtime_hours": 2,
  "task_load": 82,
  "meeting_hours": 11,
  "leave_days": 1,
  "feedback": "I feel overwhelmed and exhausted."
}
```

## Project Structure

```text
.
|-- index.html
|-- src/
|   |-- app.js
|   `-- styles.css
|-- data/
|   |-- sampleData.js
|   `-- sample_employees.json
|-- backend/
|   |-- api_server.py
|   `-- burnout_engine.py
|-- database/
|   `-- schema.sql
`-- docs/
    |-- project-report.md
    `-- uml-diagrams.md
```

## Risk Formula

The score follows the project brief:

```text
Burnout Score =
  (0.25 * Work Hours)
+ (0.20 * Overtime)
+ (0.20 * Task Load)
+ (0.15 * Meeting Count)
+ (0.20 * Negative Sentiment)
```

Inputs are normalized to a 0-100 scale before scoring.

Risk levels:

- `0-30`: Low
- `31-60`: Medium
- `61-80`: High
- `81-100`: Critical

## Suggested Extensions

- Replace the heuristic model with Random Forest or XGBoost after collecting a real labeled dataset.
- Add authentication and role-based access control.
- Store predictions in PostgreSQL or MySQL.
- Add chatbot-based wellness support.
- Add monthly forecasting using time-series models.
