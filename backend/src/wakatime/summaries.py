import json
from typing import Literal, Union
from uuid import UUID

from pydantic import BaseModel
import aiohttp

from . import (
    WakatimeAPIResponse,
    WakatimeTokens,
    WakatimeTimeframeType,
    validate_timeframe,
)


class SummaryMetadataModel(BaseModel):
    name: str


class LineChanges(SummaryMetadataModel):
    human_additions: int
    human_deletions: int
    ai_additions: int
    ai_deletions: int


class Duration(SummaryMetadataModel):
    hours: int
    minutes: int
    seconds: int
    total_seconds: float
    digital: str
    text: str
    percent: float


class GrandTotalModel(BaseModel):
    hours : int
    minutes : int
    total_seconds: float
    digital : str
    decimal : str
    text : str
    human_additions: int
    human_deletions: int
    ai_additions: int
    ai_deletions: int


class CategoryModel(Duration):
    pass


class ProjectModel(LineChanges, Duration):
    pass


class LanguageModel(Duration):
    pass


class EditorModel(Duration):
    pass


class OSModel(Duration):
    pass


class DependencyModel(Duration):
    pass


class MachineModel(Duration):
    machine_name_id: str


class BranchModel(Duration):
    pass


class EntityModel(LineChanges, Duration):
    pass


class Range(BaseModel):
    date: str
    start: str
    end: str
    text: str
    timezone: str


class SummarySections(BaseModel):
    grand_total: GrandTotalModel
    categories: list[CategoryModel]
    projects: list[ProjectModel]
    languages: list[LanguageModel]
    editors: list[EditorModel]
    operating_systems: list[OSModel]
    dependencies: list[DependencyModel]
    machines: list[MachineModel]
    # branches: list[BranchModel]
    # entities: list[EntityModel]
    range: Range


class CumulativeTotalModel(BaseModel):
    seconds: float
    text: str
    decimal: str
    digital: str


class DailyAverageModel(BaseModel):
    holidays: int
    days_including_holidays: int
    days_minus_holidays: int
    seconds: float
    text: str
    seconds_including_other_language: float
    text_including_other_language: str


class SummaryResponseModel(BaseModel):
    data: list[SummarySections]
    cumulative_total: CumulativeTotalModel
    daily_average: DailyAverageModel

    start: str
    end: str


async def get_summaries(
    tokens: WakatimeTokens,
    user : Union[Literal["current"], UUID],
    timeframe: WakatimeTimeframeType
) -> WakatimeAPIResponse[SummaryResponseModel]:
    """
    Rerturns a user's coding activity for the given time range in the summaries format.

    The summaries format aggregates heartbeats and durations so we don't need to compute them
    ourselves. 
    """
    
    # Ensure the timeframe is formatted correctly.
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format supplied")

    async with aiohttp.ClientSession() as cs:
        async with cs.get(
            f"https://wakatime.com/api/v1/users/{user}/summaries",
            headers = {
                "Authorization" : f"Bearer {tokens['access_token']}"
            },
            params = {
                **timeframe.model_dump()
            }
        ) as resp:
            status_code = resp.status
            resp_json = await resp.read()

    # If we don't get an OK response, then we must have an error.
    if status_code != 200:
        return WakatimeAPIResponse(status_code=status_code, response=None)
    
    # Otherwise, return the summary response model
    return WakatimeAPIResponse(
        status_code=status_code,
        response = SummaryResponseModel.model_validate_json(resp_json)
    )

__all__ = [
    "get_summaries"
]