"""The feature contract shared by training and serving. No fitted transforms."""
import math

INSURANCE_MAP = {"private": 0, "government": 1, "no_insurance": 2}
ACTIVITY_MAP = {"high": 0, "medium": 1, "low": 2}
MODEL_FEATURES = [
    "age", "gender", "bmi", "smoker", "diabetes", "hypertension",
    "heart_disease", "asthma", "physical_activity_level", "daily_steps",
    "sleep_hours", "stress_level", "doctor_visits_per_year",
    "hospital_admissions", "medication_count", "insurance_type",
    "previous_year_cost", "city_type_Semi_Urban", "city_type_Urban",
    "out_of_pocket_frac",
]


def normalize_category(value):
    return value.strip().lower().replace("semi urban", "semi-urban") if isinstance(value, str) else value


def encode_features(profile: dict, bmi: float) -> dict[str, float]:
    """Encode an already validated profile; fail on unknown categories."""
    values = dict(profile)
    values.update(
        bmi=round(bmi, 2),
        gender={"female": 0, "male": 1}[profile["gender_raw"]],
        smoker={"no": 0, "yes": 1}[profile["smoker_raw"]],
        physical_activity_level=ACTIVITY_MAP[profile["physical_activity_level_raw"]],
        insurance_type=INSURANCE_MAP[profile["insurance_type_raw"]],
        city_type_Semi_Urban=int(profile["city"] == "semi-urban"),
        city_type_Urban=int(profile["city"] == "urban"),
        out_of_pocket_frac=1 - profile["insurance_coverage_frac"],
    )
    result = {name: float(values[name]) for name in MODEL_FEATURES}
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError("All derived model features must be finite")
    return result
