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

## Dataset documentation display (v2.1)

Prediction and model-info responses include `dataset_status`: a `documented` or `incomplete` status, missing detail identifiers, and plain-language notes. Currency, source URL and cost definition are checked separately. A documented value is not a claim of independent verification. Missing, blank and placeholder definitions remain incomplete even when currency and source are present.

Missing documentation is shown as a neutral demo note next to the estimate, with details in “Dataset details & model limits.” Yellow warnings are reserved for profile inputs outside recorded ranges. The original documentation gap is unresolved; no currency or cost definition has been invented. Downloaded summaries retain the same structured status.

## Indian rupee display

The web interface formats cost inputs, estimates, monthly equivalents, contributions, prediction intervals and comparisons using Indian rupee labels and `Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'})`. The original model values are not converted or rescaled. Dataset documentation remains unchanged: this is an explicit demo display convention, not evidence the model was trained on Indian costs. Downloaded summaries include `display_currency` with `currency: INR`, `locale: en-IN`, `conversion_applied: false` and an explanatory note. API currency still describes training units, independently of browser presentation.

## Version 3 interface and installation

The frontend uses three validated steps with a show-all option. English and Hindi cover the form, result, model-limit notes, chart labels, scenarios, report text and key errors. API JSON remains machine-readable English. Native browser validation and print-dialog language depend on the browser. Hindi fonts and Chart.js are served locally with their license notices; there are no CDN/font requests.

A language and theme preference are stored under `careestimate-language` and `careestimate-theme`. Profiles, estimates and scenario results stay in memory. Editing the form invalidates results and clears any generated report. A scenario clones the last calculated profile and updates only the selected factor; it never writes into the form. Comparisons across different model versions/currencies are rejected. These are associations, not interventions or guaranteed savings.

**Print / Save PDF** opens the browser print dialog with a purpose-built A4 report. Choose the browser's Save as PDF destination. The report includes the estimate, available intervals, model version, optional comparisons/scenario, leading contributions and limitations. Raw form inputs are omitted. No server-side PDF service or automatic file upload is used.

The install button appears when the browser offers installation. Browser installation support varies; users may also use the browser's install/add-to-home-screen menu. `/sw.js` owns only a fixed public-shell allowlist and uses network-first caching. Its cache version is `careestimate-shell-v3`; bump it when intentionally changing the shell cache contract. It never intercepts `POST`, `/predict`, `/model-info`, `/metrics` or `/health`. Offline startup shows the cached interface and an offline notice, and requires a connection for fresh predictions. It never queues health profiles for later upload. Offline reload starts with the static example form, not the previous user's profile.

## Inference and latency metrics

LightGBM's contribution vector includes the base value and sums to its raw regression prediction. Version 3 derives the point estimate from that vector in one call rather than traversing the model twice. Regression tests compare this path with normal predictions for several example profiles. The saved model is unchanged.

`careestimate_prediction_duration_seconds` is now a Prometheus histogram, with `_bucket`, `_count` and the existing `_sum`. It counts successful inference only and remains process-local. Use a scraper to calculate percentile latency; these counters do not measure Vercel cold starts or network time.

Run a repeatable local benchmark:

```bash
python scripts/benchmark_inference.py --iterations 300
```

A local macOS arm64 run with 150 iterations per path measured median **1.389 ms** for two calls versus **1.342 ms** for one, with p95 **1.534 ms** versus **1.439 ms**. Loading the bundle took about **0.998 s**. These are warmed microbenchmarks on one synthetic example profile, not hosted performance guarantees or model-quality results. Re-run on the deployment environment before making performance claims.

## Public production address

Use **https://medical-cost-app-king-09.vercel.app** and its `/docs` API documentation. This stable team alias points to the current production deployment. An explicitly approved, alias-specific Deployment Protection Exception makes this hostname publicly accessible. The project-wide protection setting remains in place; other deployment URLs may require a Vercel login.

The older `medical-cost-app-jade.vercel.app` hostname timed out through its default edge addresses from the tested connection, even though the application worked through an alternative Vercel edge route. The team alias uses a reachable route and was verified with ordinary HTTPS, without credentials or DNS overrides. Deployment status alone is not a reachability test.

When changing deployment settings, preserve the alias-specific exception or intentionally replace it with a reviewed public domain. Check the public homepage, `/health`, `/predict`, `/sw.js`, and `/static/manifest.webmanifest` after releases. Do not distribute a preview URL that redirects visitors to Vercel authentication.
