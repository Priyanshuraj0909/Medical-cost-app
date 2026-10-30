# Offline training and evaluation

Runtime requirements already include the training dependencies. Run commands from the repository root with Python 3.12. No production model is retrained automatically.

## Required input

Use an authorized, local CSV in ignored `data/`. Its columns must match exactly:

```text
age,gender,bmi,smoker,diabetes,hypertension,heart_disease,asthma,physical_activity_level,daily_steps,sleep_hours,stress_level,doctor_visits_per_year,hospital_admissions,medication_count,insurance_type,insurance_coverage_pct,city_type,previous_year_cost,annual_medical_cost
```

Categories are case-insensitive: gender `male/female`, smoker `yes/no`, activity `low/medium/high`, insurance `private/government/no_insurance`, city `urban/semi-urban/rural`. Condition flags must be 0 or 1. Coverage uses 0–100 in CSV and 0–1 in API requests. Uninsured profiles must have zero coverage. Ages must be 18–89, matching this application's supported scope. Non-finite values and blank categories are rejected. Exact duplicate rows are removed; identical encoded profiles stay in the same split even if their targets differ.

Create `data/data-card.json` from [data-card.template.json](data-card.template.json). Fill all provenance fields and every prediction-time audit entry. The template deliberately contains unknown values and cannot train until completed. `synthetic` must be an explicit boolean. The audit records when each feature becomes available, its lookback window, and why it is known before the target period; the program checks completeness but cannot verify the assertions.

```bash
python -m training.train \
  --data data/medical_cost_prediction_dataset.csv \
  --data-card data/data-card.json \
  --output artifacts/candidate-001 \
  --seed 42 --folds 5 --coverage 0.9
```

Use a new empty output directory for each run. The command refuses to overwrite the repository's `model/` directory. Private datasets and generated artifacts are ignored by Git and excluded from deployments.

## Evaluation protocol

- Split **profile groups**, approximately 60% fitting, 20% calibration, 20% final testing. This prevents identical encoded feature profiles crossing partitions. Group sizes can change the row proportions.
- Run grouped five-fold cross-validation on the fitting portion for median, standardized Ridge, Random Forest and LightGBM. Record MAE, RMSE and R² means and standard deviations.
- Fit all four models on the fitting portion and report their held-out test metrics. LightGBM's parameters are fixed in advance; the test set is not used to select or tune the deployment candidate.
- Calibrate a symmetric split-conformal interval with absolute residuals on the calibration portion. Use the finite-sample order statistic `ceil((n + 1) * coverage)`. Clip the lower endpoint to zero because validated targets are nonnegative.
- Measure interval coverage on the final test portion and separately on test profiles inside the fitting ranges. Record the sample sizes.
- Report errors by age band, gender, city, smoking status and insurance type. Small groups need cautious interpretation; error comparisons are not a fairness certification.

The profile-group split cannot detect shared patient identity with different feature values, future-information leakage, or geographic shift. Adapt splitting to the dataset's true sampling unit and forecast horizon before real-world use. Repeatedly choosing model versions from the same test set also contaminates that test set; reserve a new final evaluation set when iterating.

## Artifacts

| File | Purpose |
| --- | --- |
| `evaluation.json` | Baseline/CV/test results, subgroup errors, coverage, split sizes, package versions and dataset hash |
| `predicted-vs-actual.svg` | Standalone held-out diagnostic plot |
| `residuals.svg` | Standalone residual diagnostic plot |
| `metadata.json` | Provenance, model version, SHA-256, fitting ranges and interval calibration |
| `lgbm_medical_cost_model.pkl` | Trusted local candidate model |

Plots contain held-out values: treat generated artifacts as sensitive when training on private data. JSON reports do not export input profiles. A fixed seed and pinned environment make the procedure repeatable; report timestamps differ between runs and binary hashes can differ across environments.

## Model promotion

Review provenance, prediction-time availability and all evaluation outputs before using a candidate. A synthetic-fixture test validates code paths; it is not a measured improvement to the serving model.

To inspect a candidate locally without replacing the bundled model:

```bash
CAREESTIMATE_MODEL_DIR=artifacts/candidate-001 uvicorn app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell: set `$env:CAREESTIMATE_MODEL_DIR = 'artifacts/candidate-001'` before running Uvicorn. Bundle paths must be trusted local paths. Pickle can execute code; a checksum detects mismatched files, not malicious bundles supplied with their own checksum.

The serving model loads once at startup. Promote by copying a reviewed model **and its matching metadata** into `model/` through a reviewed change, rerunning tests, and restarting/deploying. The offline command never does this for you. The bundled deployment needs no environment variables; generated `artifacts/` are intentionally excluded from hosting bundles.

Intervals are withheld for requests outside recorded fitting ranges. Split-conformal intervals target marginal coverage under exchangeability; they do not guarantee individual or shifted-population coverage.
