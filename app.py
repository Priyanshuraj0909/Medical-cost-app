from contextlib import asynccontextmanager
from pathlib import Path
import ctypes
import logging
import os
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
import numpy as np

from model_bundle import load_bundle
from batch import describe_rows, parse_profiles, read_csv_body
from monitoring import ServiceMetrics
from schema.dataset import dataset_status
from schema.output import PredictionResponse, BatchResponse
from schema.user_input import UserRequest, MODEL_FEATURES

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "4.0.0"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    openmp = BASE_DIR / "native/libgomp.so.1"
    if openmp.is_file():
        ctypes.CDLL(str(openmp), mode=ctypes.RTLD_GLOBAL)
    directory = Path(os.environ.get("CAREESTIMATE_MODEL_DIR", str(BASE_DIR / "model")))
    app.state.model, app.state.metadata = load_bundle(directory)
    app.state.metrics = ServiceMetrics()
    try:
        yield
    finally:
        app.state.model = None


app = FastAPI(title="CareEstimate API", version=APP_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path in {"/predict", "/metrics", "/health"} or request.url.path.startswith('/batch/'):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path in {"/", "/sw.js"} or request.url.path.startswith("/static/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; font-src 'self'; connect-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    if request.url.path == "/predict":
        request.app.state.metrics.record("validation_error", 0, [])
    # Pydantic errors can contain the whole profile or NaN/Infinity inputs.
    # Return actionable locations and messages without echoing submitted data.
    return JSONResponse(status_code=422, content={
        "detail": [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    })


@app.post("/predict", response_model=PredictionResponse)
def predict(request: UserRequest) -> dict:
    model = getattr(app.state, "model", None)
    if model is None:
        app.state.metrics.record("unavailable", 0, [])
        raise HTTPException(status_code=503, detail="Prediction service is unavailable")
    started = perf_counter()
    metadata = app.state.metadata
    features = request.model_features()
    matrix = np.array([[features[col] for col in MODEL_FEATURES]], dtype=float)
    outside = [name for name, (low, high) in metadata["observed_ranges"].items() if not low <= features[name] <= high]
    try:
        contributions = np.asarray(model.booster_.predict(matrix, pred_contrib=True, num_threads=1)[0], dtype=float)
        if contributions.shape != (len(MODEL_FEATURES) + 1,) or not np.isfinite(contributions).all():
            raise ValueError("Invalid model prediction")
        # LightGBM contributions include the base value and sum to the raw
        # regression prediction. Avoid a redundant second traversal of the model.
        prediction = float(contributions.sum())
        if not np.isfinite(prediction) or prediction < 0:
            raise ValueError("Invalid model prediction")
    except Exception:
        # Do not log exception values or tracebacks that might include profile data.
        logger.error("Model inference failed")
        app.state.metrics.record("failure", 0, [])
        raise HTTPException(status_code=503, detail="Unable to calculate an estimate. Please try again.") from None
    documentation = dataset_status(metadata["dataset"])
    warnings = [f"{name.replace('_', ' ').capitalize()} is outside the recorded training range; this estimate may be unreliable." for name in outside]
    interval = None
    uncertainty_note = "A calibrated prediction interval is unavailable for this model. The estimate does not express certainty."
    calibration = metadata.get("interval")
    if calibration is not None and not outside:
        interval = {
            "lower": round(max(0, prediction - calibration["radius"]), 2),
            "upper": round(prediction + calibration["radius"], 2),
            "nominal_coverage": calibration["nominal_coverage"],
            "measured_test_coverage": calibration["measured_test_coverage"],
        }
        uncertainty_note = "Coverage was measured on held-out data; individual and shifted-population coverage is not guaranteed."
    elif calibration is not None:
        uncertainty_note = "Prediction interval withheld because this profile is outside recorded training ranges."
    app.state.metrics.record("success", perf_counter() - started, outside)
    return {
        "predicted_medical_cost": round(prediction, 2),
        "model_version": metadata["model_version"],
        "currency": "dataset units (currency unspecified)" if "currency" in documentation.missing_details else metadata["dataset"]["currency"],
        "dataset_status": documentation.model_dump(),
        "warnings": warnings,
        "explanation": {
            "base_value": float(contributions[-1]),
            "contributions": sorted([
                {"feature": name, "contribution": float(value)}
                for name, value in zip(MODEL_FEATURES, contributions[:-1])
            ], key=lambda item: abs(item["contribution"]), reverse=True),
        },
        "prediction_interval": interval,
        "uncertainty_note": uncertainty_note,
    }


@app.post('/batch/validate', response_model=BatchResponse)
async def validate_batch(request: Request):
    rows = parse_profiles(await read_csv_body(request))
    return describe_rows(rows, 'validation')


def predict_batch_rows(rows):
    if getattr(app.state, 'model', None) is None:
        raise HTTPException(503, 'Prediction service is unavailable')
    response = describe_rows(rows, 'prediction')
    for source, result in zip(rows, response['rows']):
        if source['profile'] is None:
            continue
        try:
            result['prediction'] = predict(source['profile'])
            result['status'] = 'predicted'
            response['predicted_rows'] += 1
        except HTTPException:
            result['status'] = 'unavailable'
            result['errors'] = [{'field': 'service', 'message': 'Unable to calculate this estimate. Please try again.'}]
            response['failed_rows'] += 1
    return response


@app.post('/batch/predict', response_model=BatchResponse)
async def batch_predict(request: Request):
    rows = parse_profiles(await read_csv_body(request))
    return await run_in_threadpool(predict_batch_rows, rows)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static/index.html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health_check():
    if getattr(app.state, "model", None) is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    return {"status": "ok", "version": APP_VERSION, "model_version": app.state.metadata["model_version"], "model loaded": True}


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(BASE_DIR / "static/sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/model-info")
def model_info():
    """Public provenance and validation status; no submitted profiles."""
    metadata = app.state.metadata
    result = {key: metadata.get(key) for key in (
        "model_version", "artifact_sha256", "dataset", "validation_status",
        "historical_metrics", "observed_ranges", "interval",
    )}
    result["dataset_status"] = dataset_status(metadata["dataset"]).model_dump()
    return result


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(app.state.metrics.render(), media_type="text/plain; version=0.0.4")
