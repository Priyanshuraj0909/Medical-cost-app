# Original dataset: evidence and unresolved questions

The serving model remains the repository's original LightGBM model. Its source data is **not included**. No original dataset publisher, license, currency, collection period, geography or synthetic/real status has been verified. Do not infer these from similar online datasets.

| Property | Evidence available in this repository |
| --- | --- |
| Filename | Notebook reads `/content/medical_cost_prediction_dataset.csv` |
| Size | Saved notebook outputs show 5,000 rows |
| Raw schema | 19 input columns plus `annual_medical_cost` |
| Target meaning | Name is known; total cost versus patient out-of-pocket cost is unresolved |
| Age | Saved summary reports minimum 18, maximum 89 |
| Model features | 20 encoded features; see `schema/features.py` |
| Insurance missingness | Notebook fills 1,048 missing insurance values with `No_insurance`; the semantic correctness of this assumption is unverified |
| Historical evaluation | One random 80/20 split, seed 42; saved test MSE 268649.1462670019 and R² 0.9944922364583165 |
| Current validation | Historical results have not been reproduced; no calibrated interval exists for the serving model |

R² is not classification accuracy. Historical RMSE derived from saved MSE is approximately 518.31 in unidentified currency units. No historical MAE was saved. These numbers do not establish real-world forecasting accuracy.

The out-of-pocket fraction has saved correlation 0.856152 with the target. Establish how the target was produced and whether insurance coverage is a legitimate pre-prediction input. Strong association alone does not establish leakage. Confirm whether admissions, visits and medication counts refer to the prediction year or a preceding period: same-year utilization would be unavailable for a forecast made before that year.

The UI now explicitly asks for care utilization in the preceding 12 months. This is a clear input convention, **not evidence that the legacy model was trained with that timing**. Treat the legacy model as an educational estimator until this is resolved. Age 18–89 is an observed bound, not evidence of validation across all adults in that range.

## Recovering and validating the source

1. Obtain the original CSV and publisher's data dictionary and license.
2. Establish the currency, target, population, time period, and whether records are synthetic.
3. Verify which fields are known at the time a prediction would be made. Document lookback windows for every feature.
4. Resolve missing insurance values using the source dictionary; do not silently equate missing with uninsured.
5. Run the offline evaluation described in [TRAINING.md](TRAINING.md). Use patient-group or chronological validation if longitudinal identifiers or dates are available; the provided profile-group split cannot establish those properties.
6. Review baseline errors, subgroup counts, residuals, interval coverage, and the source license before promoting a model.

The new training script intentionally rejects missing categories. Never replace the absent original CSV with a generated dataset while retaining claims about the original model's quality.
