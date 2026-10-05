# CareEstimate — Medical Cost App

A responsive medical cost planner backed by the repository’s trained LightGBM model and FastAPI. Enter health, lifestyle, medical history, and insurance details to see an estimated annual cost and its monthly equivalent.

## Run locally

Use **Python 3.10–3.12**; Python 3.12 is used in Docker and CI. The pinned NumPy/SciPy versions do not support newer Python versions.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

On macOS, if LightGBM reports a missing OpenMP library, install it with `brew install libomp`.

- Web app: http://localhost:8000
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The app loads the model during startup and verifies feature names and order. Files are resolved relative to `app.py`, so loading is independent of your working directory.

## API

`GET /` serves the web interface. `GET /health` returns status, model version, and `model loaded`; it returns HTTP 503 if the model is unavailable.

`POST /predict` accepts this request:

```json
{
  "age": 35,
  "gender_raw": "female",
  "height_cm": 165,
  "weight_kg": 65,
  "city": "urban",
  "smoker_raw": "no",
  "physical_activity_level_raw": "medium",
  "daily_steps": 7000,
  "sleep_hours": 7,
  "stress_level": 4,
  "diabetes": 0,
  "hypertension": 0,
  "heart_disease": 0,
  "asthma": 0,
  "doctor_visits_per_year": 3,
  "hospital_admissions": 0,
  "medication_count": 0,
  "previous_year_cost": 5000,
  "insurance_type_raw": "private",
  "insurance_coverage_frac": 0.8
}
```

Response for this example using the included model:

```json
{"predicted_medical_cost": 1094.90}
```

Categories are case-insensitive and trimmed:

| Field | Values |
| --- | --- |
| `gender_raw` | `male`, `female` |
| `smoker_raw` | `yes`, `no` |
| `city` | `urban`, `semi-urban` (also `semi urban`), `rural` |
| `physical_activity_level_raw` | `low`, `medium`, `high` |
| `insurance_type_raw` | `private`, `government`, `no_insurance` |
| Condition flags | `0`, `1` |

Insurance coverage is a fraction from 0 to 1 in the API; the web form accepts a percentage. BMI and out-of-pocket fraction are derived automatically. Negative counts/costs, invalid categories, zero height/weight, non-finite numbers, and out-of-range age/sleep/stress/coverage return HTTP 422. Prediction failures return HTTP 503 without exposing internal errors.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests exercise the actual model, feature engineering, category normalization, invalid inputs, page/assets/docs, health checks, and prediction failures. GitHub Actions runs tests, builds the Docker image, and checks the running container on pushes and pull requests.

## Docker

```bash
docker build -t medical-cost-app .
docker run --rm -p 8000:8000 medical-cost-app
```

The image uses Python 3.12, installs OpenMP, runs as a non-root user, and includes a health check. `PORT` defaults to 8000 and can be overridden (adjust the port mapping too).

## Deploy on Vercel

The project uses Vercel’s FastAPI preset with Python 3.12 (`.python-version`). `vercel.json` sets the function timeout and excludes development files. The model and web assets remain available in the deployment.

Import this repository into Vercel and select the FastAPI framework, or run `npx vercel --prod` from this folder after signing in. No environment variables are required.

Reference: [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi).

## Deploy on Render

`render.yaml` defines one Docker web service with `/health` readiness checks. Both the web interface and API run in the same service, with no separate frontend hosting required.

1. Push these changes to your GitHub repository.
2. In Render, create a **Blueprint** and connect `Priyanshuraj0909/medical-cost-app`.
3. Review the service configuration from `render.yaml`, then deploy.
4. Visit the generated service URL and confirm `/health` and a form prediction work.

The configuration requests the free plan. Review current plan availability and limitations in Render before deploying. Hosting credentials are not needed locally, and no public deployment is created just by adding these files.

References: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Blueprint specification](https://render.com/docs/blueprint-spec), [health checks](https://render.com/docs/health-checks).

## Project structure

```text
app.py                    FastAPI routes, startup, model inference
schema/                   Request validation and feature engineering
model/                    Original trained LightGBM pickle
static/                   HTML, CSS, and JavaScript web interface
tests/                    API and model integration tests
LGBMRegressor_and_feature_engineering.ipynb  Original training notebook
Dockerfile                Container packaging
render.yaml               Render deployment configuration
.github/workflows/ci.yml  Tests and container checks
```

## Model and data limitations

The original training dataset is not included, and its currency, provenance, and intended population have not been verified. Estimates are therefore labeled as **dataset currency units**, rather than asserting rupees or another currency. The monthly figure is the annual prediction divided by twelve, not a separate prediction. The notebook alone does not establish performance on new users.

This is a model estimate, not a bill or insurance quote. Confirm insurance coverage and local care prices before making spending decisions. The app does not save submitted profile data or log request bodies. Only load model pickle files from trusted sources.
