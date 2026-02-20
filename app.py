from fastapi import FastAPI
import pickle
import numpy as np
from schema.output import PredictionResponse
from schema.user_input import UserRequest , UserFeatures ,MODEL_FEATURES

with open("model/lgbm_medical_cost_model.pkl", "rb") as f:
    model = pickle.load(f)


app = FastAPI(title="Medical Cost Prediction API")
MODEL_VERSION = '1.0.0'

@app.post("/predict",response_model=PredictionResponse)
def predict(request: UserRequest) -> dict:
    user = UserFeatures(**request.model_dump())
    features = user.model_features()

    X = np.array([[features[col] for col in MODEL_FEATURES]])

    prediction = model.booster_.predict(X)

    return {
        "predicted_medical_cost": float(prediction[0])
    }

@app.get('/')
def home():
    return {'message' : 'Calculate your total health expenditure'}

@app.get('/health')
def health_check():
    return {
        'status' : 'ok',
        'version' : MODEL_VERSION,
        'model loaded' : model is not None
    }
