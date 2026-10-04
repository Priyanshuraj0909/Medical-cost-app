import math
import pytest
from fastapi.testclient import TestClient
from app import app
from schema.user_input import UserFeatures, MODEL_FEATURES


@pytest.fixture
def payload():
    return dict(age=35, gender_raw="female", height_cm=165, weight_kg=65,
                city="urban", smoker_raw="no", physical_activity_level_raw="medium",
                daily_steps=7000, sleep_hours=7, stress_level=4, diabetes=0,
                hypertension=0, heart_disease=0, asthma=0, doctor_visits_per_year=3,
                hospital_admissions=0, medication_count=0, previous_year_cost=5000,
                insurance_type_raw="private", insurance_coverage_frac=.8)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_page_assets_health_and_docs(client):
    assert 'CareEstimate' in client.get('/').text
    for path in ['/static/app.js', '/static/style.css', '/docs', '/openapi.json']:
        assert client.get(path).status_code == 200
    assert client.get('/health').json()['model loaded'] is True


def test_prediction_uses_actual_model(client, payload):
    response = client.post('/predict', json=payload)
    assert response.status_code == 200
    value = response.json()['predicted_medical_cost']
    assert math.isfinite(value) and value >= 0
    features = UserFeatures(**payload).model_features()
    expected = app.state.model.booster_.predict([[features[name] for name in MODEL_FEATURES]], num_threads=1)[0]
    assert value == round(float(expected), 2)


@pytest.mark.parametrize('field,value', [('height_cm', 0), ('weight_kg', -1), ('age', -1), ('age', 121),
    ('insurance_coverage_frac', 1.1), ('insurance_type_raw', 'typo'), ('smoker_raw', 'maybe'),
    ('city', 'unknown'), ('gender_raw', 'unknown'), ('physical_activity_level_raw', 'extreme'),
    ('diabetes', 2), ('heart_disease', -1), ('sleep_hours', 25), ('daily_steps', -1),
    ('medication_count', -1), ('previous_year_cost', -1), ('hospital_admissions', -1),
    ('doctor_visits_per_year', -1), ('stress_level', 11)])
def test_bad_inputs_return_422(client, payload, field, value):
    payload[field] = value
    assert client.post('/predict', json=payload).status_code == 422


def test_missing_inputs(client):
    assert client.post('/predict', json={}).status_code == 422


def test_feature_mapping(payload):
    payload.update(city=' Semi Urban ', gender_raw=' Male ', smoker_raw='YES',
                   insurance_type_raw='Government', physical_activity_level_raw='HIGH')
    features = UserFeatures(**payload).model_features()
    assert list(features) == MODEL_FEATURES
    assert features['city_type_Semi_Urban'] == 1 and features['city_type_Urban'] == 0
    assert features['gender'] == features['smoker'] == features['insurance_type'] == 1
    assert features['physical_activity_level'] == 0
    assert features['bmi'] == 23.88
    assert features['out_of_pocket_frac'] == pytest.approx(.2)


def test_unavailable_model(client, payload):
    model = app.state.model
    app.state.model = None
    try:
        assert client.get('/health').status_code == 503
        assert client.post('/predict', json=payload).status_code == 503
    finally:
        app.state.model = model


def test_invalid_prediction(client, payload, monkeypatch):
    monkeypatch.setattr(app.state.model.booster_, 'predict', lambda *args, **kwargs: [float('nan')])
    assert client.post('/predict', json=payload).status_code == 503
