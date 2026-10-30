"""Validated public inputs and the shared raw training profile."""
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schema.features import MODEL_FEATURES, encode_features, normalize_category


class Profile(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    age: Annotated[int, Field(ge=18, le=89, description="Age in years; observed training population: 18–89")]
    gender_raw: Literal["male", "female"]
    city: Literal["urban", "semi-urban", "rural"]
    smoker_raw: Literal["yes", "no"]
    physical_activity_level_raw: Literal["low", "medium", "high"]
    daily_steps: Annotated[int, Field(ge=0, le=100000)]
    sleep_hours: Annotated[float, Field(ge=0, le=24)]
    stress_level: Annotated[int, Field(ge=1, le=10)]
    diabetes: Literal[0, 1]
    heart_disease: Literal[0, 1]
    hypertension: Literal[0, 1] = 0
    asthma: Literal[0, 1] = 0
    doctor_visits_per_year: Annotated[int, Field(ge=0, description="Visits in the preceding 12 months")] = 7
    hospital_admissions: Annotated[int, Field(ge=0, description="Admissions in the preceding 12 months")] = 2
    medication_count: Annotated[int, Field(ge=0)]
    previous_year_cost: Annotated[float, Field(ge=0, description="Preceding 12 months' cost, in dataset currency units")]
    insurance_type_raw: Literal["private", "government", "no_insurance"]
    insurance_coverage_frac: Annotated[float, Field(ge=0, le=1, description="Insurance coverage as a fraction, not a percentage")]

    @field_validator("insurance_type_raw", "smoker_raw", "physical_activity_level_raw", "gender_raw", "city", mode="before")
    @classmethod
    def normalize_categories(cls, value):
        return normalize_category(value)

    @model_validator(mode="after")
    def consistent_insurance(self):
        if self.insurance_type_raw == "no_insurance" and self.insurance_coverage_frac != 0:
            raise ValueError("No insurance requires zero insurance coverage")
        return self


class UserRequest(Profile):
    height_cm: Annotated[float, Field(gt=0, le=300)]
    weight_kg: Annotated[float, Field(gt=0, le=700)]

    @model_validator(mode="after")
    def finite_bmi(self):
        try:
            bmi = self.weight_kg / (self.height_cm / 100) ** 2
        except (ZeroDivisionError, OverflowError):
            raise ValueError("Height and weight must produce a finite BMI") from None
        if not math.isfinite(bmi):
            raise ValueError("Height and weight must produce a finite BMI")
        return self

    def model_features(self) -> dict[str, float]:
        bmi = round(self.weight_kg / (self.height_cm / 100) ** 2, 2)
        return encode_features(self.model_dump(), bmi)


class UserFeatures(UserRequest):
    """Compatibility name for callers using the original feature interface."""
