"""Describe missing dataset documentation without inventing provenance or units."""
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel


class DatasetStatus(BaseModel):
    status: Literal["incomplete", "documented"]
    missing_details: list[Literal["currency", "source", "cost_definition"]]
    notes: list[str]


def documented(value) -> bool:
    """A populated description is documented, not independently verified."""
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    return bool(text) and text not in {"unknown", "unspecified", "not specified", "n/a", "tbd"} and not text.startswith("unverified")


def dataset_status(dataset: dict) -> DatasetStatus:
    source = dataset.get("source_url")
    try:
        parsed = urlparse(source.strip()) if isinstance(source, str) else None
    except ValueError:
        parsed = None
    checks = [
        ("currency", documented(dataset.get("currency")),
         "Currency is not specified; amounts are shown in dataset units."),
        ("source", bool(parsed and parsed.scheme in {"https", "http"} and parsed.netloc),
         "The original dataset source is not recorded."),
        ("cost_definition", documented(dataset.get("target_definition")),
         "Whether costs mean total spending or patient out-of-pocket spending is not established."),
    ]
    missing = [(name, note) for name, present, note in checks if not present]
    return DatasetStatus(
        status="incomplete" if missing else "documented",
        missing_details=[name for name, _ in missing],
        notes=[note for _, note in missing],
    )
