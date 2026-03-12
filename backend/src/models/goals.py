from pydantic import BaseModel, Field
from src.db.models import GoalEnum

class GoalResponseModel(BaseModel):
    goal_id : int
    timeframe : GoalEnum
    minutes : int

    progress : float

class GoalCreationRequest(BaseModel):
    timeframe : GoalEnum = Field(examples=[GoalEnum.DAILY, GoalEnum.WEEKLY])
    minutes : int = Field(examples=[15, 30, 60], gt=0)

class GoalUpdateRequest(BaseModel):
    timeframe : GoalEnum | None = Field(default=None)
    minutes : int | None = Field(default=None, gt=0)