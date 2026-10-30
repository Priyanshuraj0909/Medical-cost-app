"""Behavioral regressions for feature parity, explanations and model scope."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import app
from model_bundle import load_bundle
from schema.user_input import UserRequest
from training.train import RAW_FEATURES, conformal_radius, prepare_data, train


@pytest.fixture
def profile():
    return dict(age=35, gender_raw="female", height_cm=165, weight_kg=65, city="urban",
                smoker_raw="no", physical_activity_level_raw="medium", daily_steps=7000,
                sleep_hours=7, stress_level=4, diabetes=0, hypertension=0, heart_disease=0,
                asthma=0, doctor_visits_per_year=3, hospital_admissions=0, medication_count=0,
                previous_year_cost=5000, insurance_type_raw="private", insurance_coverage_frac=.8)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_explanations_reconcile_and_uncertainty_is_honest(client, profile):
    result = client.post('/predict', json=profile).json()
    explained = result['explanation']['base_value'] + sum(x['contribution'] for x in result['explanation']['contributions'])
    assert explained == pytest.approx(result['predicted_medical_cost'], abs=.0051)
    assert len(result['explanation']['contributions']) == 20
    assert result['prediction_interval'] is None
    assert 'unavailable' in result['uncertainty_note']
    assert result['warnings']


@pytest.mark.parametrize('changes', [dict(age=17), dict(age=90), dict(insurance_type_raw='no_insurance'),
    dict(height_cm=1e-200), dict(previous_year_cost=float('inf')), dict(unknown_field=1)])
def test_scope_and_consistency(client, profile, changes):
    profile.update(changes)
    if any(isinstance(value, float) and math.isinf(value) for value in changes.values()):
        # JSON clients reject non-standard infinity literals, so send it explicitly.
        response = client.post('/predict', content=json.dumps(profile), headers={'Content-Type': 'application/json'})
    else:
        response = client.post('/predict', json=profile)
    assert response.status_code == 422


def test_uninsured_zero_coverage_is_valid(client, profile):
    profile.update(insurance_type_raw='no_insurance', insurance_coverage_frac=0)
    assert client.post('/predict', json=profile).status_code == 200


def test_monitoring_contains_only_aggregates_and_security_headers(client, profile):
    profile.update(daily_steps=20000)
    response = client.post('/predict', json=profile)
    assert any('Daily steps' in message for message in response.json()['warnings'])
    assert response.headers['cache-control'] == 'no-store'
    assert 'default-src' in client.get('/').headers['content-security-policy']
    assert 'unsafe-inline' not in client.get('/').headers['content-security-policy']
    metrics = client.get('/metrics').text
    assert 'careestimate_requests_total{outcome="success"} 1' in metrics
    assert 'feature="daily_steps"} 1' in metrics
    assert '20000' not in metrics and 'gender_raw' not in metrics
    assert client.get('/model-info').json()['dataset']['source_url'] is None


def test_calibrated_interval_and_outside_suppression(client, profile):
    app.state.metadata['interval'] = dict(radius=100, nominal_coverage=.9, measured_test_coverage=.88)
    result = client.post('/predict', json=profile).json()
    interval = result['prediction_interval']
    assert interval['upper'] - interval['lower'] == pytest.approx(200)
    profile['daily_steps'] = 20000
    result = client.post('/predict', json=profile).json()
    assert result['prediction_interval'] is None
    assert 'withheld' in result['uncertainty_note']


def test_corrupt_bundle_fails_before_deserialization(tmp_path):
    source = Path('model')
    metadata = json.loads((source / 'metadata.json').read_text())
    (tmp_path / 'metadata.json').write_text(json.dumps(metadata))
    (tmp_path / metadata['artifact_file']).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='checksum'):
        load_bundle(tmp_path)


def test_training_and_serving_feature_parity(profile):
    request = UserRequest(**profile)
    raw = {name: profile[name] for name in RAW_FEATURES if name in profile}
    raw.update(gender='Female', smoker='No', physical_activity_level='Medium', insurance_type='Private',
               city_type='Urban', insurance_coverage_pct=80, bmi=65 / 1.65 ** 2, annual_medical_cost=1234)
    X, y, _, _, _ = prepare_data(pd.DataFrame([raw]))
    assert X.iloc[0].to_dict() == request.model_features()
    assert y.tolist() == [1234]
    raw['insurance_type'] = ''
    with pytest.raises(ValueError, match='CSV row'):
        prepare_data(pd.DataFrame([raw]))


def test_conformal_uses_finite_sample_order_statistic():
    assert conformal_radius(np.arange(1, 20), .9) == 18
    with pytest.raises(ValueError, match='Not enough'):
        conformal_radius([1, 2], .99)


def test_offline_pipeline_produces_loadable_independent_bundle(tmp_path):
    """Synthetic fixture verifies the pipeline, not the production model's quality."""
    rng = np.random.default_rng(42)
    rows = []
    for index in range(150):
        coverage = int(rng.integers(30, 91))
        rows.append(dict(age=int(rng.integers(18, 90)), gender='Male' if index % 2 else 'Female',
            bmi=round(float(rng.uniform(18, 40)), 2), smoker='No', diabetes=index % 2,
            hypertension=0, heart_disease=0, asthma=0, physical_activity_level='Medium',
            daily_steps=int(rng.integers(1000, 15000)), sleep_hours=7, stress_level=4,
            doctor_visits_per_year=int(rng.integers(0, 10)), hospital_admissions=index % 4,
            medication_count=index % 5, insurance_type='Private', insurance_coverage_pct=coverage,
            city_type=['Urban', 'Semi-Urban', 'Rural'][index % 3], previous_year_cost=5000 + index,
            annual_medical_cost=round(10000 * (1 - coverage / 100) + index % 4 * 500 + float(rng.uniform(0, 500)), 2)))
    # Exact duplicates are removed; repeated feature profiles stay together.
    rows.append(rows[0].copy())
    repeated = rows[1].copy(); repeated['annual_medical_cost'] += 10; rows.append(repeated)
    data = tmp_path / 'fixture.csv'; pd.DataFrame(rows).to_csv(data, index=False)
    card = dict(source_url='https://example.invalid/synthetic-test-fixture', license='Test fixture only',
        currency='TEST', population='Synthetic test profiles', collection_period='Generated in test',
        synthetic=True, target_definition='Artificial test target; no real-world validity',
        prediction_time_audit={name: 'Artificial value generated before the test target' for name in RAW_FEATURES})
    card_path = tmp_path / 'card.json'; card_path.write_text(json.dumps(card))
    output = tmp_path / 'candidate'
    report = train(data, card_path, output, folds=2)
    model, metadata = load_bundle(output)
    assert model.n_features_in_ == 20
    assert report['exact_duplicate_rows_removed'] == 1
    assert sum(report['split'][name] for name in ('fit', 'calibration', 'test')) == 151
    assert set(report['models']) == {'median', 'ridge', 'random_forest', 'lightgbm'}
    assert 0 <= metadata['interval']['measured_test_coverage'] <= 1
    assert metadata['artifact_sha256'] == hashlib.sha256((output / metadata['artifact_file']).read_bytes()).hexdigest()
    assert (output / 'residuals.svg').is_file()
    with pytest.raises(ValueError, match='empty output'):
        train(data, card_path, output, folds=2)
