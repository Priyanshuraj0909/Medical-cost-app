from pydantic import Field , BaseModel , model_validator
from typing import Annotated
insurance_map = {
    "no_insurance": 2,
    "government": 1,
    "private": 0,
}

activity_map = {
    "low": 2,
    "medium": 1,
    "high": 0,
}

# -----------------------
# MODEL FEATURE CONTRACT
# -----------------------
MODEL_FEATURES = [
    "age",
    "gender",
    "bmi",
    "smoker",
    "diabetes",
    "hypertension",
    "heart_disease",
    "asthma",
    "physical_activity_level",
    "daily_steps",
    "sleep_hours",
    "stress_level",
    "doctor_visits_per_year",
    "hospital_admissions",
    "medication_count",
    "insurance_type",
    "previous_year_cost",
    "city_type_Semi_Urban",
    "city_type_Urban",
    "out_of_pocket_frac",
]


# =====================================================
# PUBLIC API MODEL (THIS IS WHAT /docs SHOWS)
# =====================================================
class UserRequest(BaseModel):
    insurance_coverage_frac: Annotated[
        float,
        Field(
            ...,
            ge=0,
            le=1,
            description="Fraction of medical cost covered by insurance (0–1). Example: 0.8"
        )
    ]
    insurance_type_raw: Annotated[
        str,
        Field(description="Type of insurance: private, government, or no_insurance")
    ]

    smoker_raw: Annotated[
        str,
        Field(description="Smoking status: yes or no")
    ]
    physical_activity_level_raw: Annotated[
        str,
        Field(description="Physical activity level: low, medium, or high")
    ]
    gender_raw: Annotated[
        str,
        Field(description="Gender: male or female")
    ]
    city: Annotated[
        str,
        Field(description="City type: urban, semi-urban, or rural")
    ]

    height_cm: Annotated[
        float,
        Field(description="Height in centimeters. Used to calculate BMI")
    ]
    weight_kg: Annotated[
        float,
        Field(description="Weight in kilograms. Used to calculate BMI")
    ]

    age: Annotated[
        int,
        Field(description="Age in years")
    ]
    medication_count: Annotated[
        int,
        Field(description="Number of medications currently taken")
    ]
    heart_disease: Annotated[
        int,
        Field(description="1 if patient has heart disease, else 0")
    ]
    diabetes: Annotated[
        int,
        Field(description="1 if patient has diabetes, else 0")
    ]
    previous_year_cost: Annotated[
        float,
        Field(description="Total medical cost in the previous year")
    ]

    daily_steps: Annotated[
        int,
        Field(description="Average number of steps per day")
    ]
    sleep_hours: Annotated[
        float,
        Field(description="Average sleep duration per day in hours")
    ]
    stress_level: Annotated[
        int,
        Field(ge=1, le=10, description="Stress level on a scale of 1–10")
    ]

    hypertension: Annotated[
        int,
        Field(default=0, description="1 if patient has hypertension, else 0")
    ]
    asthma: Annotated[
        int,
        Field(default=0, description="1 if patient has asthma, else 0")
    ]
    doctor_visits_per_year: Annotated[
        int,
        Field(default=7, description="Number of doctor visits per year")
    ]
    hospital_admissions: Annotated[
        int,
        Field(default=2, description="Number of hospital admissions per year")
    ]


# =====================================================
# INTERNAL MODEL (NOT EXPOSED TO /docs)
# =====================================================
class UserFeatures(UserRequest):
    gender: int = 0
    smoker: int = 0
    physical_activity_level: int = 1
    insurance_type: int = 0

    city_type_Urban: int = 0
    city_type_Semi_Urban: int = 0

    bmi: float = 0.0
    out_of_pocket_frac: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def derive_features(cls, values):
        insurance = values.get("insurance_type_raw", "").strip().lower()
        activity = values.get("physical_activity_level_raw", "").strip().lower()
        city = values.get("city", "").strip().lower()
        smoker = values.get("smoker_raw", "").strip().lower()
        gender = values.get("gender_raw", "").strip().lower()

        values["insurance_type"] = insurance_map.get(insurance, 2)
        values["physical_activity_level"] = activity_map.get(activity, 1)
        values["smoker"] = 1 if smoker == "yes" else 0
        values["gender"] = 1 if gender == "male" else 0

        values["city_type_Urban"] = 1 if city == "urban" else 0
        values["city_type_Semi_Urban"] = 1 if city in {"semi-urban", "semi urban"} else 0

        coverage = values.get("insurance_coverage_frac", 0)
        values["out_of_pocket_frac"] = 1 - coverage

        height_m = values.get("height_cm", 0) / 100
        weight = values.get("weight_kg", 0)
        values["bmi"] = round(weight / (height_m ** 2), 2) if height_m > 0 else 0.0

        return values

    def model_features(self) -> dict:
        data = self.model_dump()
        return {k: data[k] for k in MODEL_FEATURES}

