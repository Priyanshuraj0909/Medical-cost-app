# Operating CareEstimate

`GET /health` verifies model readiness and returns application and model versions. A checksum or feature-contract mismatch prevents startup. `GET /model-info` exposes provenance, recorded ranges, historical evaluation status and any interval calibration.

`GET /metrics` returns Prometheus text with bounded aggregate counters:

- `careestimate_requests_total{outcome="success|validation_error|unavailable|failure"}`
- `careestimate_prediction_duration_seconds_sum`: accumulated successful inference time, including contribution calculation
- `careestimate_out_of_range_total{feature="..."}`: successful profiles outside recorded ranges, one counter per known model feature

Metrics do not retain request bodies, submitted values or user identifiers. Validation errors return field locations and messages without echoing inputs. Inference failures log a fixed message without request data or exception values. Prediction responses and metrics use `Cache-Control: no-store`.

Counters are in-memory and **per process**. They reset on restart and are not globally accurate across workers or Vercel function instances. Scrape instances on a long-lived deployment if useful. Out-of-range counts flag range excursions, not a statistical drift test or a measurement of accuracy. Accuracy monitoring requires authorized, subsequently observed target values and a separate evaluation process. No claim of PSI monitoring or production error monitoring is made.

The application does not persist profiles. Comparisons live in browser memory until cleared or the page closes; summary downloads are user-controlled and may include sensitive model explanations. This does not control hosting-provider access logs or external infrastructure policies. No browser analytics or external fonts are loaded.

## Checks

```bash
python -m pytest -q
npm ci
npx playwright install chromium
npm run test:browser
```

Browser tests launch and stop their own loopback API server on a free port. They exercise real predictions, explanations, comparison, export, error recovery, desktop/mobile layout and axe WCAG checks. Set `PYTHON_BIN=.venv/bin/python` when needed. To use an installed browser, set `CHROME_PATH` to its executable. Set `SCREENSHOT_PATH` to save the mobile test screenshot. Do not point browser tests at production: they own a local server and use synthetic example inputs.

Automated accessibility checks cover only the tested states and do not replace manual assistive-technology testing. GitHub Actions runs API/training tests, browser checks, the Docker build and a container readiness check. Development-only Node dependencies are excluded from deployment.

## Release behavior

API v2 retains `predicted_medical_cost` and adds version, currency, warnings, contributions, uncertainty status and optional intervals. Stricter validation now rejects ages outside 18–89, unknown fields and nonzero coverage with `no_insurance`. Consumers that send extra fields or expect a one-field response must adapt.

The historical model is unchanged. Improvements to interface and validation are not evidence of improved predictive accuracy. Review the [data card](DATA_CARD.md) before making claims about the model.
