"""Reproducible offline evaluation: python -m training.train --help."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from pydantic import Field
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from schema.features import MODEL_FEATURES, encode_features
from schema.user_input import Profile

TARGET = "annual_medical_cost"
CATEGORY_COLUMNS = {
    "gender": "gender_raw", "smoker": "smoker_raw",
    "physical_activity_level": "physical_activity_level_raw",
    "insurance_type": "insurance_type_raw", "city_type": "city",
}
RAW_FEATURES = [
    "age", "gender", "bmi", "smoker", "diabetes", "hypertension", "heart_disease",
    "asthma", "physical_activity_level", "daily_steps", "sleep_hours", "stress_level",
    "doctor_visits_per_year", "hospital_admissions", "medication_count",
    "insurance_type", "insurance_coverage_pct", "city_type", "previous_year_cost",
]


class TrainingRow(Profile):
    bmi: float = Field(gt=0, allow_inf_nan=False)
    annual_medical_cost: float = Field(ge=0, allow_inf_nan=False)


def prepare_data(frame: pd.DataFrame):
    """Validate every raw row, then use exactly the serving feature encoder.

    Blank insurance values are rejected: absence of a value is not evidence of
    no insurance. A documented source-specific correction must happen upstream.
    """
    expected = set(RAW_FEATURES + [TARGET])
    if set(frame.columns) != expected:
        raise ValueError(f"CSV columns must match the documented schema; missing={sorted(expected - set(frame.columns))}, extra={sorted(set(frame.columns) - expected)}")
    clean = frame.drop_duplicates().reset_index(drop=True)
    rows, targets, profiles = [], [], []
    for index, raw in enumerate(clean.to_dict(orient="records")):
        try:
            data = {CATEGORY_COLUMNS.get(key, key): value for key, value in raw.items() if key != "insurance_coverage_pct"}
            data["insurance_coverage_frac"] = float(raw["insurance_coverage_pct"]) / 100
            row = TrainingRow.model_validate(data)
            profile = row.model_dump()
            rows.append(encode_features(profile, row.bmi))
            targets.append(row.annual_medical_cost)
            profiles.append(profile)
        except (ValueError, TypeError, KeyError):
            # Do not include sensitive row contents in error messages.
            raise ValueError(f"CSV row {index + 2} is invalid; check documented types, categories and ranges") from None
    X = pd.DataFrame(rows, columns=MODEL_FEATURES, dtype=float)
    y = np.asarray(targets)
    groups = pd.util.hash_pandas_object(X, index=False).to_numpy()
    return X, y, pd.DataFrame(profiles), groups, len(frame) - len(clean)


def validate_data_card(card):
    required = ("source_url", "license", "currency", "population", "collection_period", "target_definition")
    if any(not isinstance(card.get(key), str) or not card[key].strip() for key in required):
        raise ValueError("Data card requires explicit source, license, currency, population, collection period and target definition")
    if not isinstance(card.get("synthetic"), bool):
        raise ValueError("Data card must explicitly identify whether the data is synthetic")
    audit = card.get("prediction_time_audit", {})
    if set(audit) != set(RAW_FEATURES) or any(not isinstance(v, str) or len(v.strip()) < 10 for v in audit.values()):
        raise ValueError("Document when each raw feature is known before prediction in prediction_time_audit")


def score(y, predicted):
    return {"mae": float(mean_absolute_error(y, predicted)), "rmse": float(math.sqrt(mean_squared_error(y, predicted))), "r2": float(r2_score(y, predicted)) if len(y) > 1 else None}


def conformal_radius(residuals, coverage):
    """Finite-sample split-conformal order statistic, without interpolation."""
    residuals = np.asarray(residuals, dtype=float)
    if residuals.ndim != 1 or not len(residuals) or not np.isfinite(residuals).all() or (residuals < 0).any() or not 0 < coverage < 1:
        raise ValueError("Invalid conformal calibration inputs")
    rank = math.ceil((len(residuals) + 1) * coverage)
    if rank > len(residuals):
        raise ValueError("Not enough calibration rows for the requested coverage")
    return float(np.partition(residuals, rank - 1)[rank - 1])


def scatter_svg(path, x, y, xlabel, ylabel):
    """Standalone diagnostic plot, no plotting dependency or external assets."""
    def scale(values, low, high):
        span = max(float(np.ptp(values)), 1.0)
        return low + (np.asarray(values) - np.min(values)) / span * (high - low)
    xs, ys = scale(x, 75, 615), scale(y, 325, 30)
    points = ''.join(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="2" fill="#265b46" opacity=".35"/>' for a, b in zip(xs, ys))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 400" role="img" aria-labelledby="title">
<title id="title">{ylabel} versus {xlabel}</title><rect width="660" height="400" fill="white"/>
<path d="M75 25V325H625" fill="none" stroke="#213d35"/>{points}
<g font-family="sans-serif" font-size="12" fill="#213d35"><text x="270" y="385">{xlabel}</text>
<text transform="translate(16 250) rotate(-90)">{ylabel}</text>
<text x="75" y="346">{float(np.min(x)):.1f}</text><text x="570" y="346">{float(np.max(x)):.1f}</text>
<text x="22" y="325">{float(np.min(y)):.1f}</text><text x="22" y="30">{float(np.max(y)):.1f}</text></g></svg>'''
    path.write_text(svg)


def train(data_path: Path, card_path: Path, output: Path, seed=42, folds=5, coverage=.9):
    card = json.loads(card_path.read_text())
    validate_data_card(card)
    if output.resolve() == Path("model").resolve() or output.exists() and any(output.iterdir()):
        raise ValueError("Use a new, empty output directory; the serving model must not be overwritten")
    if not 2 <= folds <= 10 or not 0 < coverage < 1:
        raise ValueError("Use 2–10 folds and coverage strictly between zero and one")
    X, y, profiles, groups, duplicates = prepare_data(pd.read_csv(data_path, keep_default_na=False))
    if len(X) < 100 or len(np.unique(groups)) < 30:
        raise ValueError("At least 100 validated rows and 30 distinct profiles are required")
    development, test = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed).split(X, y, groups))
    fit_local, calibration_local = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=seed + 1).split(X.iloc[development], y[development], groups[development]))
    fit, calibration = development[fit_local], development[calibration_local]
    group_sets = [set(groups[indices]) for indices in (fit, calibration, test)]
    disjoint = not any(group_sets[a] & group_sets[b] for a, b in ((0, 1), (0, 2), (1, 2)))
    if not disjoint:
        raise ValueError("Identical profiles crossed evaluation partitions")
    if len(np.unique(groups[fit])) < folds:
        raise ValueError("Not enough distinct training profiles for cross-validation")
    candidates = {
        "median": DummyRegressor(strategy="median"),
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1)),
        "random_forest": RandomForestRegressor(n_estimators=150, min_samples_leaf=2, random_state=seed, n_jobs=1),
        "lightgbm": LGBMRegressor(n_estimators=500, learning_rate=.05, random_state=seed, n_jobs=1, verbosity=-1, deterministic=True, force_col_wise=True),
    }
    comparisons = {}
    cv = GroupKFold(n_splits=folds)
    for name, candidate in candidates.items():
        results = cross_validate(candidate, X.iloc[fit], y[fit], groups=groups[fit], cv=cv,
                                 scoring={"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"}, error_score="raise")
        candidate.fit(X.iloc[fit], y[fit])
        comparisons[name] = {
            "cv": {metric: {"mean": float(np.mean(results[f"test_{metric}"]) * (-1 if metric != "r2" else 1)), "std": float(np.std(results[f"test_{metric}"]))} for metric in ("mae", "rmse", "r2")},
            "held_out_test": score(y[test], candidate.predict(X.iloc[test])),
        }
    # Algorithm and parameters are fixed in advance; the test set does not select
    # or tune the deployment candidate. Calibration is never used for fitting.
    model = candidates["lightgbm"]
    predicted = model.predict(X.iloc[test])
    if not np.isfinite(predicted).all() or (predicted < 0).any():
        raise ValueError("Candidate returned invalid predictions; do not promote this model")
    residuals = np.abs(y[calibration] - model.predict(X.iloc[calibration]))
    radius = conformal_radius(residuals, coverage)
    lower, upper = np.maximum(0, predicted - radius), predicted + radius
    observed = {name: [float(X.iloc[fit][name].min()), float(X.iloc[fit][name].max())] for name in MODEL_FEATURES}
    inside = np.array([all(observed[name][0] <= row[name] <= observed[name][1] for name in MODEL_FEATURES) for row in X.iloc[test].to_dict(orient="records")])
    covered = (y[test] >= lower) & (y[test] <= upper)
    interval = {"radius": radius, "nominal_coverage": coverage, "measured_test_coverage": float(covered.mean()), "test_rows": len(test),
                "in_range_test_rows": int(inside.sum()), "in_range_test_coverage": float(covered[inside].mean()) if inside.any() else None}
    subgroups = {}
    for name in ("gender_raw", "city", "smoker_raw", "insurance_type_raw"):
        values = profiles.iloc[test][name].to_numpy()
        subgroups[name] = {str(value): {"count": int((values == value).sum()), **score(y[test][values == value], predicted[values == value])} for value in sorted(set(values))}
    age_bands = pd.cut(profiles.iloc[test]["age"], bins=[17, 39, 59, 89], labels=["18–39", "40–59", "60–89"]).astype(str).to_numpy()
    subgroups["age_band"] = {band: {"count": int((age_bands == band).sum()), **score(y[test][age_bands == band], predicted[age_bands == band])} for band in sorted(set(age_bands))}
    output.mkdir(parents=True, exist_ok=True)
    artifact = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    (output / "lgbm_medical_cost_model.pkl").write_bytes(artifact)
    data_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    metadata = {
        "model_version": f"candidate-{data_hash[:12]}", "artifact_file": "lgbm_medical_cost_model.pkl",
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "dataset": {**card, "target": TARGET, "sha256": data_hash, "rows": len(X)},
        "validation_status": "Offline grouped holdout evaluation; see evaluation.json. External validity is not established.",
        "observed_ranges": observed, "interval": interval,
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "seed": seed, "folds": folds,
        "split": {"fit": len(fit), "calibration": len(calibration), "test": len(test), "identical_profile_groups_disjoint": disjoint},
        "exact_duplicate_rows_removed": duplicates, "models": comparisons, "interval": interval,
        "subgroup_errors": subgroups, "dataset_sha256": data_hash,
        "environment": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "lightgbm", "pydantic")},
        "limitations": ["Random profile-group splits do not establish temporal or geographic generalization.", "Subgroup error differences are diagnostic, not a fairness certification.", "Conformal coverage assumes exchangeable calibration and future observations.", "Prediction-time availability is documented by the data provider; code cannot prove temporal validity."],
    }
    for filename, content in (("metadata.json", metadata), ("evaluation.json", report)):
        (output / filename).write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")
    scatter_svg(output / "predicted-vs-actual.svg", y[test], predicted, "Actual cost", "Predicted cost")
    scatter_svg(output / "residuals.svg", predicted, y[test] - predicted, "Predicted cost", "Actual minus predicted cost")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--data-card", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--coverage", type=float, default=.9)
    parser.add_argument("--mlflow-tracking-uri", help="Optional explicit MLflow store/server URI; no tracking occurs unless supplied")
    parser.add_argument("--mlflow-experiment", default="CareEstimate")
    args = parser.parse_args()
    try:
        report = train(args.data, args.data_card, args.output, args.seed, args.folds, args.coverage)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Training failed: {exc}\n")
    if args.mlflow_tracking_uri:
        from training.tracking import log_experiment
        try:
            run_id = log_experiment(args.output, args.mlflow_tracking_uri, args.mlflow_experiment)
        except Exception:
            parser.exit(2, "Experiment tracking failed. Candidate artifacts were preserved; check the tracking configuration.\n")
        print(json.dumps({"mlflow_run_id": run_id}))
    print(json.dumps({"output": str(args.output), "lightgbm_test": report["models"]["lightgbm"]["held_out_test"]}, indent=2))


if __name__ == "__main__":
    main()
