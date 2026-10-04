from contextlib import asynccontextmanager
from pathlib import Path
import logging
import pickle

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import numpy as np

from schema.output import PredictionResponse
from schema.user_input import UserRequest, UserFeatures, MODEL_FEATURES

BASE_DIR = Path(__file__).resolve().parent
MODEL_VERSION = "1.0.0"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with (BASE_DIR / "model/lgbm_medical_cost_model.pkl").open("rb") as file:
        model = pickle.load(file)
    actual = [name.replace("-", "_") for name in model.booster_.feature_name()]
    if actual != MODEL_FEATURES:
        raise RuntimeError("Model feature contract does not match application features")
    app.state.model = model
    yield
    app.state.model = None


app = FastAPI(title="Medical Cost Prediction API", version=MODEL_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.post("/predict", response_model=PredictionResponse)
def predict(request: UserRequest) -> dict:
    model = getattr(app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="Prediction service is unavailable")
    features = UserFeatures(**request.model_dump()).model_features()
    matrix = np.array([[features[col] for col in MODEL_FEATURES]], dtype=float)
    try:
        prediction = float(model.booster_.predict(matrix, num_threads=1)[0])
        if not np.isfinite(prediction) or prediction < 0:
            raise ValueError("Invalid model prediction")
    except Exception:
        logger.exception("Model prediction failed")
        raise HTTPException(status_code=503, detail="Unable to calculate an estimate. Please try again.") from None
    return {"predicted_medical_cost": round(prediction, 2)}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static/index.html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health_check():
    loaded = getattr(app.state, "model", None) is not None
    if not loaded:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    return {"status": "ok", "version": MODEL_VERSION, "model loaded": loaded}
