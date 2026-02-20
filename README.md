# Medical Cost Prediction API

A FastAPI-based web service that predicts medical insurance costs using a Light Gradient Boosting Machine (LightGBM) model. This application takes patient health data and lifestyle information as input and returns an estimated annual medical cost.

## Overview

This project implements a machine learning prediction API that estimates medical expenses based on various health and demographic factors. The model is trained using LightGBM, a high-performance gradient boosting framework, and serves predictions through a REST API built with FastAPI.

## Features

- **REST API Endpoints** for real-time medical cost predictions
- **Health Check** endpoint for monitoring API status
- **Input Validation** using Pydantic schemas
- **Docker Support** for containerized deployment
- **LightGBM Model** for accurate cost predictions

## Project Structure

```
medical/
├── app.py                          # Main FastAPI application
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker configuration
├── README.md                       # This file
├── LGBMRegressor_and_feature_engineering.ipynb  # Model training notebook
├── model/
│   └── lgbm_medical_cost_model.pkl # Trained LightGBM model
└── schema/
    ├── user_input.py              # Request schema and feature mappings
    └── output.py                  # Response schema
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip or conda package manager

### Local Setup

1. Clone or download the repository:
```bash
cd medical
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`

### Docker Setup

Build and run the application using Docker:

```bash
# Build the Docker image
docker build -t medical-cost-api .

# Run the container
docker run -p 8000:8000 medical-cost-api
```

## Dependencies

- **fastapi** (0.127.0) - Web framework for building APIs
- **uvicorn** (0.40.0) - ASGI server
- **pydantic** (2.12.5) - Data validation and settings management
- **numpy** (1.26.4) - Numerical computing
- **pandas** (2.2.3) - Data manipulation
- **scipy** (1.11.4) - Scientific computing
- **lightgbm** (4.6.0) - Gradient boosting library

## API Endpoints

### 1. Home Endpoint
```
GET /
```
Returns a welcome message.

**Response:**
```json
{
  "message": "Calculate your total health expenditure"
}
```

### 2. Health Check
```
GET /health
```
Returns the API health status and model information.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model loaded": true
}
```

### 3. Predict Medical Cost
```
POST /predict
```
Predicts medical insurance cost based on patient health data.

**Request Body:**
```json
{
  "age": 45,
  "gender": "M",
  "bmi": 24.5,
  "smoker": false,
  "diabetes": false,
  "hypertension": false,
  "heart_disease": false,
  "asthma": false,
  "physical_activity_level": "high",
  "daily_steps": 10000,
  "sleep_hours": 7,
  "stress_level": 5,
  "doctor_visits_per_year": 3,
  "hospital_admissions": 0,
  "medication_count": 0,
  "insurance_coverage_frac": 0.8,
  "insurance_type": "private",
  "previous_year_cost": 5000,
  "city_type": "Urban",
  "out_of_pocket_fraction": 0.2
}
```

**Response:**
```json
{
  "predicted_medical_cost": 12000.50
}
```

## Model Features

The model uses the following 20 features for predictions:

- **Demographics:** age, gender
- **Health Metrics:** bmi, smoker, diabetes, hypertension, heart_disease, asthma
- **Lifestyle:** physical_activity_level, daily_steps, sleep_hours, stress_level
- **Medical History:** doctor_visits_per_year, hospital_admissions, medication_count
- **Insurance:** insurance_type, insurance_coverage_frac
- **Financial:** previous_year_cost, out_of_pocket_frac
- **Location:** city_type

## Schema Details

### Feature Mappings

**Insurance Type:**
- `no_insurance`: 2
- `government`: 1
- `private`: 0

**Activity Level:**
- `low`: 2
- `medium`: 1
- `high`: 0

## Development

### Model Training

The model was trained and evaluated using the Jupyter notebook:
- `LGBMRegressor_and_feature_engineering.ipynb`

This notebook contains:
- Exploratory data analysis
- Feature engineering
- Model training
- Hyperparameter tuning
- Model evaluation

### Running Locally with Hot Reload

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Interactive API Documentation

Once the server is running, visit:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## Model Performance

The LightGBM model is trained to predict medical costs with high accuracy. The trained model is serialized and stored at:
```
model/lgbm_medical_cost_model.pkl
```

## Error Handling

The API includes validation for all input fields:
- Required fields must be provided
- Numeric fields have specified ranges
- Invalid input will return a 422 Unprocessable Entity response with validation details

## Deployment

### Production Deployment

For production environments:

1. **Use a production ASGI server** (e.g., Gunicorn with Uvicorn workers):
```bash
gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

2. **Use the provided Dockerfile** for containerized deployment

3. **Set environment variables** for configuration as needed

## Version

Current API Version: **1.0.0**

## License

This project is provided as-is for medical cost prediction purposes.

## Support

For issues or questions about the API, please refer to the FastAPI documentation or contact the development team.

## Notes

- The model requires specific feature engineering to maintain prediction accuracy
- Input values should be within reasonable ranges for health and demographic data
- The model performs best on data similar to its training distribution
