import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app
from batch import MAX_CSV_BYTES

TEMPLATE = Path('static/batch-template.csv').read_text()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def send(client, text, operation='validate'):
    return client.post('/batch/' + operation, content=text, headers={'Content-Type': 'text/csv'})


def modified(**changes):
    reader = csv.DictReader(io.StringIO(TEMPLATE))
    profile = next(reader)
    profile.update(changes)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerow(profile)
    return output.getvalue().splitlines()[1]


def test_preview_and_partial_prediction(client):
    text = TEMPLATE.rstrip() + '\n' + modified(age='17') + '\n' + modified(hospital_admissions='3')
    preview = send(client, '\ufeff' + text)
    assert preview.status_code == 200
    assert preview.headers['Cache-Control'] == 'no-store'
    data = preview.json()
    assert (data['valid_rows'], data['invalid_rows'], data['predicted_rows']) == (2, 1, 0)
    assert all(row['prediction'] is None for row in data['rows'])
    response = send(client, text, 'predict')
    assert response.status_code == 200
    data = response.json()
    assert data['predicted_rows'] == 2 and data['failed_rows'] == 0
    assert [row['status'] for row in data['rows']] == ['predicted', 'invalid', 'predicted']
    assert [row['row'] for row in data['rows']] == [2, 3, 4]
    assert data['rows'][0]['prediction']['predicted_medical_cost'] == 1094.9
    assert 'profile' not in response.text


@pytest.mark.parametrize('text,status', [('', 400), ('age\n35', 400),
    (TEMPLATE.replace('age,', 'age,age,', 1), 400),
    (TEMPLATE + '\x00', 400), (TEMPLATE + '"unterminated', 400),
    ('x' * (MAX_CSV_BYTES + 1), 413),
    (TEMPLATE + (TEMPLATE.splitlines()[1] + '\n') * 50, 413)])
def test_invalid_files(client, text, status):
    assert send(client, text).status_code == status


def test_encoding_and_media_type(client):
    assert send(client, b'\xff').status_code == 400
    assert client.post('/batch/validate', json={}).status_code == 415


def test_row_errors_and_privacy(client):
    text = TEMPLATE.splitlines()[0] + '\n' + modified(gender_raw='private-secret-value') + '\n' + modified(insurance_type_raw='no_insurance') + '\n' + TEMPLATE.splitlines()[1].rsplit(',', 1)[0]
    response = send(client, text)
    assert response.status_code == 200
    assert response.json()['invalid_rows'] == 3
    assert 'private-secret-value' not in response.text
    assert 'input' not in response.text


def test_fifty_profiles_and_service_failure(client, monkeypatch):
    text = TEMPLATE.splitlines()[0] + '\n' + (TEMPLATE.splitlines()[1] + '\n') * 50
    assert send(client, text).json()['valid_rows'] == 50
    monkeypatch.setattr(app.state, 'model', None)
    assert send(client, TEMPLATE, 'predict').status_code == 503


def test_row_inference_failure_is_reported(client, monkeypatch):
    monkeypatch.setattr(app.state.model.booster_, 'predict', lambda *args, **kwargs: [float('nan')])
    data = send(client, TEMPLATE, 'predict').json()
    assert data['failed_rows'] == 1 and data['predicted_rows'] == 0
    assert data['rows'][0]['status'] == 'unavailable'
