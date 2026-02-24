from datetime import date, datetime
from pydantic import BaseModel


class LanguageBreakdownModel(BaseModel):
    name: str
    total_seconds: float


class DurationResponseModel(BaseModel):
    date: "date"
    total_seconds: float
    languages: list[LanguageBreakdownModel]

    last_cached_at: datetime


class BulkDurationResponseModel(BaseModel):
    durations: list[DurationResponseModel]


__all__ = [
    "LanguageBreakdownModel",
    "DurationResponseModel",
    "BulkDurationResponseModel",
]
