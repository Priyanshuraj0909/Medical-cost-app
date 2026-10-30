"""Load a trusted local model bundle and verify its declared integrity."""
import hashlib
import json
import math
from pathlib import Path
import pickle

from schema.features import MODEL_FEATURES


def load_bundle(directory: Path):
    metadata = json.loads((directory / "metadata.json").read_text())
    filename = metadata["artifact_file"]
    if Path(filename).name != filename:
        raise ValueError("Model artifact must be a file inside the bundle")
    artifact = (directory / filename).read_bytes()
    if hashlib.sha256(artifact).hexdigest() != metadata["artifact_sha256"]:
        raise ValueError("Model artifact checksum does not match its metadata")
    # Pickle is only appropriate for trusted, administrator-provisioned bundles.
    model = pickle.loads(artifact)
    actual = [name.replace("-", "_") for name in model.booster_.feature_name()]
    if actual != MODEL_FEATURES:
        raise ValueError("Model feature contract does not match application features")
    if not isinstance(metadata["model_version"], str) or not metadata["model_version"]:
        raise ValueError("Model version is required")
    for name, bounds in metadata["observed_ranges"].items():
        if name not in MODEL_FEATURES or len(bounds) != 2 or not all(math.isfinite(x) for x in bounds) or bounds[0] > bounds[1]:
            raise ValueError("Invalid observed feature range")
    interval = metadata.get("interval")
    if interval is not None:
        radius = interval["radius"]
        coverage = interval["nominal_coverage"]
        measured = interval["measured_test_coverage"]
        if not all(math.isfinite(x) for x in (radius, coverage, measured)) or radius < 0 or not 0 < coverage < 1 or not 0 <= measured <= 1:
            raise ValueError("Invalid interval calibration metadata")
    return model, metadata
