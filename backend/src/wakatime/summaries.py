from pydantic import BaseModel
import aiohttp

from . import WakatimeAPIResponse, WakatimeTokens, WakatimeTimeframeType, validate_timeframe

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
    total_seconds: int
    digital: str
    text: str
    percent: float

class GrandTotalModel(LineChanges, Duration):
    pass

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
    branches: list[BranchModel]
    entities: list[EntityModel]
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
    data: SummarySections
    cumulative_total: CumulativeTotalModel
    daily_average: DailyAverageModel

    start: str
    end: str


async def get_summaries(
    tokens : WakatimeTokens,
    timeframe : WakatimeTimeframeType
) -> WakatimeAPIResponse[SummaryResponseModel]:
    
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format supplied")

    # TODO: