# TimeSense

TimeSense estimates the time needed for recipes, lecture notes, and assignments
using the pretrained Gemini API. It does not train a model.

## Architecture

```text
React/Vite (upload or camera) --> FastAPI
                                      |
                         SHA-256 SQLite response cache
                                      |
                         Gemini multimodal JSON extraction
                                      |
                         Pydantic validation + EMA calibration
                                      |
                    timer / feedback / reports and plots
```

## Features

- PDF, JPEG, PNG, and WebP uploads sent directly to Gemini without OCR.
- Browser camera capture through `getUserMedia`.
- Strict structured Gemini output with Pydantic validation and one retry.
- Four separate few-shot examples in `prompts/few_shot.json`.
- SQLite tables for tasks, estimates, feedback, and per-user speed factors.
- Exponential moving-average calibration using `actual / estimated`.
- Countdown timer with browser completion notifications.
- Evaluation script for category baselines, prompt variants, MAE, MAPE,
  within-20-percent accuracy, and MAE plots.

## Setup

### Backend

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env; never put it in frontend files.
uvicorn backend.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` if the backend is not at `http://localhost:8000`.
Camera capture uses the phone's rear camera by default. Camera access requires
HTTPS or localhost and browser camera permission. For local phone testing, serve
the frontend over HTTPS (or use a secure tunnel such as an approved university
development tunnel); a plain HTTP LAN address is normally blocked by mobile
browsers. With Vite's dev proxy, the frontend can call the backend through the
same phone-accessible origin.

### Evaluation

Copy the example data to `data/evaluation.csv`, add held-out records, and run:

```powershell
python evaluate.py --input data/evaluation.csv --reports reports
```

The evaluation CSV must contain `category` and `actual_minutes`. Optional
prediction columns are `gemini_estimate`, `plain_zero_shot`, `final_prompt`, and
`with_speed_factor`. Keep few-shot examples separate from this test data.
For a labeled perception CSV, add columns such as `predicted_category` and
`predicted_page_count`, then run with `--perception path\to\perception.csv`.
The script writes perception accuracy alongside the time-estimation results.

## Deploying to Render

The repository includes [render.yaml](./render.yaml) for a two-service deployment:
`timesense-api` (FastAPI) and `timesense-frontend` (React static site). In Render,
choose **New > Blueprint**, connect this repository, and apply the blueprint.
Render will prompt for the secret `GEMINI_API_KEY`; enter it in Render's
environment settings and never commit it.

The free plan uses `/tmp/timesense.db`, so cache and feedback data are ephemeral.
Use a persistent database or paid disk before production use. The generated
frontend URL is configured for the API's CORS allowlist by the blueprint.

## Tests

```powershell
pytest
```
