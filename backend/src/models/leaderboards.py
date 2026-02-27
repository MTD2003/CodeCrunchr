from pydantic import BaseModel
from uuid import UUID

from .users import WakatimeProfile

class LeaderboardRanking(BaseModel):
    user_id : UUID
    profile : WakatimeProfile | None
    rank : int
    total_seconds : float

class LeaderboardResponse(BaseModel):
    leaderboard: list[LeaderboardRanking]

__all__ = [
    "LeaderboardRanking",
    "LeaderboardResponse"
]