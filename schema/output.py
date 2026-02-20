from pydantic import BaseModel , Field
from typing import Annotated

class PredictionResponse(BaseModel):
    predicted_medical_cost : float = Field(... , description='total apporximated cost',examples=['Rs. 12000.50']) 