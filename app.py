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
import numpy as np

from model_bundle import load_bundle
from monitoring import ServiceMetrics
from schema.output import PredictionResponse
from schema.user_input import UserRequest, MODEL_FEATURES

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "2.0.0"
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
    if request.url.path in {"/predict", "/metrics", "/health"}:
        response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/" or request.url.path.startswith("/static/"):
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
        prediction = float(model.booster_.predict(matrix, num_threads=1)[0])
        contributions = np.asarray(model.booster_.predict(matrix, pred_contrib=True, num_threads=1)[0], dtype=float)
        if not np.isfinite(prediction) or prediction < 0 or contributions.shape != (len(MODEL_FEATURES) + 1,) or not np.isfinite(contributions).all():
            raise ValueError("Invalid model prediction")
        if not np.isclose(contributions.sum(), prediction, rtol=1e-6, atol=1e-6):
            raise ValueError("Feature contributions do not reconcile with the prediction")
    except Exception:
        # Do not log exception values or tracebacks that might include profile data.
        logger.error("Model inference failed")
        app.state.metrics.record("failure", 0, [])
        raise HTTPException(status_code=503, detail="Unable to calculate an estimate. Please try again.") from None
    warnings = [
        "The original dataset's currency, provenance and exact cost definition are unverified."
    ] if metadata["dataset"].get("currency") is None or metadata["dataset"].get("source_url") is None else []
    warnings.extend(f"{name.replace('_', ' ').capitalize()} is outside the recorded training range; this estimate may be unreliable." for name in outside)
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
        "currency": metadata["dataset"].get("currency") or "unverified dataset currency units",
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


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static/index.html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health_check():
    if getattr(app.state, "model", None) is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    return {"status": "ok", "version": APP_VERSION, "model_version": app.state.metadata["model_version"], "model loaded": True}


@app.get("/model-info")
def model_info():
    """Public provenance and validation status; no submitted profiles."""
    metadata = app.state.metadata
    return {key: metadata.get(key) for key in (
        "model_version", "artifact_sha256", "dataset", "validation_status",
        "historical_metrics", "observed_ranges", "interval",
    )}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(app.state.metrics.render(), media_type="text/plain; version=0.0.4")
