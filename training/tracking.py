"""Explicit, optional experiment logging. No automatic external uploads."""
import json
from pathlib import Path


def log_experiment(output: Path, tracking_uri: str, experiment_name="CareEstimate") -> str:
    try:
        from mlflow.tracking import MlflowClient
    except ImportError:
        raise ValueError("Install requirements-training.txt to enable optional MLflow tracking") from None
    report = json.loads((output / "evaluation.json").read_text())
    metadata = json.loads((output / "metadata.json").read_text())
    client = MlflowClient(tracking_uri=tracking_uri)
    experiment = client.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id if experiment else client.create_experiment(experiment_name)
    run = client.create_run(experiment_id, tags={"model_version": metadata["model_version"], "dataset_sha256": report["dataset_sha256"], "dataset_synthetic": str(metadata["dataset"]["synthetic"]).lower()})
    run_id = run.info.run_id
    try:
        for key in ("seed", "folds"):
            client.log_param(run_id, key, report[key])
        for name, values in report["models"].items():
            for metric, value in values["held_out_test"].items():
                if value is not None:
                    client.log_metric(run_id, f"{name}.test.{metric}", value)
            for metric, stats in values["cv"].items():
                client.log_metric(run_id, f"{name}.cv.{metric}", stats["mean"])
        client.log_metric(run_id, "interval.test_coverage", report["interval"]["measured_test_coverage"])
        # Only the explicit candidate bundle is logged, never the input CSV.
        for filename in ("evaluation.json", "metadata.json", "lgbm_medical_cost_model.pkl", "predicted-vs-actual.svg", "residuals.svg"):
            client.log_artifact(run_id, str(output / filename), artifact_path="candidate")
        client.set_terminated(run_id, status="FINISHED")
    except Exception:
        client.set_terminated(run_id, status="FAILED")
        raise
    return run_id
