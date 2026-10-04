from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    predicted_medical_cost: float = Field(
        ge=0, allow_inf_nan=False,
        description="Estimated annual medical cost in the training dataset's currency units",
        examples=[12000.50],
    )
