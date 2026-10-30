"""Real local MLflow integration; optional dependency is never used by serving."""
import json
import pytest


def test_mlflow_roundtrip_tracks_artifacts_without_the_source_csv(tmp_path):
    pytest.importorskip('mlflow')
    from mlflow.tracking import MlflowClient
    from training.tracking import log_experiment
    output = tmp_path / 'candidate'; output.mkdir()
    report = dict(seed=42, folds=5, dataset_sha256='fixture-sha',
                  models={'lightgbm': {'held_out_test': {'mae': 12.5}, 'cv': {'mae': {'mean': 13.0}}}},
                  interval={'measured_test_coverage': .9})
    metadata = {'model_version': 'fixture', 'dataset': {'synthetic': True}}
    (output / 'evaluation.json').write_text(json.dumps(report))
    (output / 'metadata.json').write_text(json.dumps(metadata))
    for name in ('lgbm_medical_cost_model.pkl', 'predicted-vs-actual.svg', 'residuals.svg'):
        (output / name).write_bytes(b'Explicit test artifact')
    uri = (tmp_path / 'tracking').as_uri()
    run_id = log_experiment(output, uri, 'Integration test')
    client = MlflowClient(tracking_uri=uri)
    run = client.get_run(run_id)
    assert run.info.status == 'FINISHED'
    assert run.data.metrics['lightgbm.test.mae'] == 12.5
    assert run.data.params['seed'] == '42'
    assert run.data.tags['dataset_synthetic'] == 'true'
    artifacts = client.list_artifacts(run_id, 'candidate')
    assert len(artifacts) == 5
    assert not any(artifact.path.endswith('.csv') for artifact in artifacts)
