<div align="center">

# ✚ CareEstimate

### A clearer picture of your medical costs.

A medical cost planner for people exploring annual healthcare budgets, powered by a trained LightGBM model and a FastAPI prediction service.

[![Build](https://github.com/Priyanshuraj0909/medical-cost-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Priyanshuraj0909/medical-cost-app/actions/workflows/ci.yml)
![License: Not specified](https://img.shields.io/badge/license-not_specified-lightgrey)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LightGBM](https://img.shields.io/badge/ML-LightGBM-426B3F)

**[Live Demo](https://medical-cost-app-jade.vercel.app)** · **[API Docs](https://medical-cost-app-jade.vercel.app/docs)** · **[Report an Issue](https://github.com/Priyanshuraj0909/medical-cost-app/issues)**

</div>

---

## Contents

[About](#about-the-project) · [Getting Started](#getting-started) · [Usage](#usage) · [Testing](#testing) · [Deployment](#deployment) · [Roadmap](#roadmap) · [Contributing](#contributing) · [License](#license)

## About the Project

CareEstimate turns a health profile into an estimated annual medical cost. Its responsive web interface collects demographic, lifestyle, medical history, and insurance details, then sends them to the repository’s trained LightGBM model through FastAPI.

The project provides both a browser experience for exploring costs and a documented REST API for developers integrating predictions into other applications.

### Key Features

- **Personalized predictions:** Annual estimates from the included model, with a monthly equivalent for budgeting.
- **Responsive interface:** Desktop and mobile layouts, an example profile, loading states, and clear error messages.
- **Validated prediction API:** Typed request schemas, category normalization, automatic BMI calculation, and a startup check of model feature names and order.
- **Deployment and verification:** Vercel configuration, Docker packaging, a Render Blueprint, and automated API/model tests in GitHub Actions.

### Built With

| Layer | Technologies |
| --- | --- |
| Web interface | HTML5, CSS3, JavaScript |
| API | Python, FastAPI, Uvicorn, Pydantic |
| Model and numerical processing | LightGBM, scikit-learn, NumPy, pandas, SciPy |
| Testing and CI | pytest, HTTPX, GitHub Actions |
| Hosting and packaging | Vercel, Docker, Render configuration |

### How It Works

```mermaid
flowchart LR
    A[Health profile] --> B[Input validation]
    B --> C[Feature engineering]
    C --> D[LightGBM model]
    D --> E[Annual cost estimate]
    E --> F[Monthly equivalent]
```

> [!NOTE]
> Costs are displayed in **dataset currency units** because the original dataset’s currency has not been verified. The monthly figure is the annual estimate divided by twelve.

## Getting Started

### Prerequisites

- **Python 3.12** recommended; the pinned dependencies support Python 3.10–3.12.
- **Git** and **pip**.
- An **OpenMP runtime** for LightGBM. Docker installs this automatically.
- **Docker** only if you prefer running a container.

On macOS, install OpenMP if LightGBM reports a missing library:

```bash
brew install libomp
```

On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y libgomp1
```

### Installation

1. **Clone the repository.**

   ```bash
   git clone https://github.com/Priyanshuraj0909/medical-cost-app.git
   cd medical-cost-app
   ```

2. **Create and activate a virtual environment.**

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, use an installed Python 3.12 interpreter:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies.**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the application.**

   ```bash
   uvicorn app:app --reload --host 127.0.0.1 --port 8000
   ```

Open **[localhost:8000](http://localhost:8000)**. No account, database, or environment variables are required.

### Run with Docker

```bash
docker build -t medical-cost-app .
docker run --rm -p 8000:8000 medical-cost-app
```

The image runs as a non-root user, includes OpenMP, and checks `/health`. Its internal `PORT` defaults to `8000`.

## Usage

### Web Interface

1. Open the [live app](https://medical-cost-app-jade.vercel.app) or your local instance.
2. Enter your personal details, lifestyle, existing conditions, care history, and insurance coverage.
3. Select **Calculate my estimate** to view the annual prediction and monthly equivalent.
4. Change any input and calculate again to update the result. **Use an example** restores the sample profile.

<!-- Screenshot placeholder: add an image at docs/images/careestimate.png, then uncomment:
![CareEstimate interface showing a health profile and annual cost estimate](docs/images/careestimate.png)
-->

### API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web interface |
| `POST` | `/predict` | Annual medical cost prediction |
| `GET` | `/health` | Service status and model readiness |
| `GET` | `/docs` | Interactive Swagger documentation |
| `GET` | `/redoc` | ReDoc API reference |

### Prediction Example

Run this against a local instance. Replace the host with the live URL to call the deployed API.

```bash
curl --request POST http://localhost:8000/predict \
  --header 'Content-Type: application/json' \
  --data '{
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
  }'
```

Example response from the included model:

```json
{
  "predicted_medical_cost": 1094.9
}
```

<details>
<summary><strong>Input categories and validation</strong></summary>

| Field | Accepted values |
| --- | --- |
| `gender_raw` | `male`, `female` |
| `smoker_raw` | `yes`, `no` |
| `city` | `urban`, `semi-urban`, `rural`; `semi urban` is also accepted |
| `physical_activity_level_raw` | `low`, `medium`, `high` |
| `insurance_type_raw` | `private`, `government`, `no_insurance` |
| Condition flags | `0` or `1` |

Categories are trimmed and case-insensitive. The API accepts insurance coverage as a fraction from `0` to `1`; the web form accepts a percentage. BMI and the out-of-pocket fraction are derived automatically.

Invalid categories, non-finite numbers, negative counts/costs, zero height/weight, and out-of-range bounded inputs return **HTTP 422**. Model unavailability or prediction failures return **HTTP 503**.

</details>

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite covers real model inference, feature engineering, category normalization, invalid inputs, page/assets/docs, readiness checks, and prediction failures. GitHub Actions runs tests, builds the Docker image, and checks a running container on pushes and pull requests.

## Deployment

### Vercel

The app is deployed at **[medical-cost-app-jade.vercel.app](https://medical-cost-app-jade.vercel.app)**. The connected GitHub repository deploys automatically when changes are pushed to `main`.

To deploy your own copy, import the repository into Vercel using the **FastAPI** preset. Alternatively, sign in and deploy with the CLI:

```bash
npx vercel login
npx vercel --prod
```

- `.python-version` selects Python 3.12.
- `vercel.json` configures the function and excludes development files.
- `vercel_build.py` bundles OpenMP from the Linux build machine; the app preloads it before loading LightGBM.
- The model and web assets are included; no environment variables are required.

See [Vercel’s FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi) for platform details.

### Render

A `render.yaml` Blueprint is included for Docker-based hosting. Connect your repository through **New → Blueprint**, review the service configuration, and deploy. The interface and API share one service, with `/health` configured as the health check. Review Render’s current plan options before deploying.

## Project Structure

```text
medical-cost-app/
├── app.py                       # API routes, startup, model inference
├── schema/                      # Validation and feature engineering
├── model/                       # Original trained LightGBM model
├── static/                      # Web interface and assets
├── tests/                       # API and model integration tests
├── .github/workflows/ci.yml     # Automated tests and Docker checks
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Development dependencies
├── .python-version              # Vercel Python version
├── vercel.json                  # Vercel configuration
├── vercel_build.py              # OpenMP bundling for Vercel
├── Dockerfile                   # Container packaging
├── render.yaml                  # Render Blueprint
└── LGBMRegressor_and_feature_engineering.ipynb
                                 # Original training notebook
```

## Roadmap

Potential future improvements; these features are not implemented yet:

- [ ] Document the training dataset’s source, currency, and intended population.
- [ ] Add reproducible model evaluation and publish measured performance.
- [ ] Improve accessibility and add automated browser tests.
- [ ] Add scenario comparisons and downloadable estimate summaries.

## Contributing

Contributions are welcome through issues and pull requests.

1. Open an issue describing the bug or proposed improvement.
2. Fork the repository and create a focused feature branch.
3. Make your changes and update relevant documentation.
4. Run `python -m pytest -q`; add meaningful tests for behavior changes.
5. Submit a pull request explaining the change and how you verified it.

Keep request schemas, feature mappings, and model feature order consistent. Changes to the model should include their data source, training method, and evaluation results. Avoid committing personal health data, secrets, virtual environments, or generated files.

## Model Scope and Privacy

The original training dataset is not included. Its provenance, currency, intended population, and predictive performance on new users have not been verified. The training notebook and serialized model are provided for exploration and development.

The application does not save submitted profiles or log request bodies. Only load pickle models from trusted sources.

> [!IMPORTANT]
> Predictions are estimates, not bills or insurance quotes. Confirm policy coverage and local care prices before using them to plan spending.

## License

**No license has been specified.** This repository currently contains no `LICENSE` file. Do not assume MIT, Apache 2.0, or another open-source license applies. The project owner should select a license and add its terms before granting broader reuse permissions.

---

<div align="center">

**CareEstimate** · Built for a more informed tomorrow.

[Try the App](https://medical-cost-app-jade.vercel.app) · [Explore the API](https://medical-cost-app-jade.vercel.app/docs)

</div>
