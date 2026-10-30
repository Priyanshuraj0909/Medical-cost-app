from typing import Literal
from pydantic import BaseModel, Field
from schema.dataset import DatasetStatus


class FeatureContribution(BaseModel):
    feature: str
    contribution: float = Field(allow_inf_nan=False)


class Explanation(BaseModel):
    base_value: float = Field(allow_inf_nan=False)
    contributions: list[FeatureContribution]
    note: str = "Contributions explain this model's estimate, not causal effects or guaranteed savings."


class PredictionInterval(BaseModel):
    lower: float = Field(ge=0, allow_inf_nan=False)
    upper: float = Field(ge=0, allow_inf_nan=False)
    nominal_coverage: float = Field(gt=0, lt=1)
    measured_test_coverage: float = Field(ge=0, le=1)
    method: str = "split conformal"


class PredictionResponse(BaseModel):
    predicted_medical_cost: float = Field(ge=0, allow_inf_nan=False, description="Annual estimate in dataset currency units")
    model_version: str
    currency: str = "dataset units (currency unspecified)"
    dataset_status: DatasetStatus
    warnings: list[str]
    explanation: Explanation
    prediction_interval: PredictionInterval | None = None
    uncertainty_note: str


class BatchError(BaseModel):
    field: str
    message: str


class BatchRow(BaseModel):
    row: int = Field(ge=2)
    status: Literal['valid', 'invalid', 'predicted', 'unavailable']
    errors: list[BatchError]
    prediction: PredictionResponse | None = None


class BatchResponse(BaseModel):
    operation: Literal['validation', 'prediction']
    total_rows: int = Field(ge=1, le=50)
    valid_rows: int = Field(ge=0, le=50)
    invalid_rows: int = Field(ge=0, le=50)
    predicted_rows: int = Field(ge=0, le=50)
    failed_rows: int = Field(ge=0, le=50)
    rows: list[BatchRow]
