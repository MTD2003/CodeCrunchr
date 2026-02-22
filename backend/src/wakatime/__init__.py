from typing import Type, TypedDict, Generic, TypeVar, TypeAlias
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from ..utils.env import get_required_env

WAKA_CLIENT_ID = get_required_env("WAKA_APP_ID")
WAKA_CLIENT_SECRET = get_required_env("WAKA_APP_SECRET")
WAKA_REDIRECT_URI = get_required_env("WAKA_REDIRECT_URI")

# Token dict


class WakatimeTokens(TypedDict):
    user_id : UUID
    access_token: str
    refresh_token: str


# Response Wrapper

T = TypeVar("T")


class WakatimeAPIResponseIsNone(Exception):
    pass


class WakatimeAPIResponse(Generic[T]):
    response: T | None
    status_code: int

    def __init__(self, status_code: int, response: T | None) -> None:
        self.status_code = status_code
        self.response = response

    def unwrap(self) -> T:
        if not self.response:
            raise WakatimeAPIResponseIsNone
        return self.response

    def get(self) -> T | None:
        return self.response

# Range vs Start/End date helpers

class WakatimeRangeTimeframe(BaseModel):
    range : str

class WakatimeStartEndTimeframe(BaseModel):
    start : str
    end : str

class InvalidTimeframeValue(Exception):
    pass

WakatimeTimeframeType = Type[WakatimeStartEndTimeframe | WakatimeRangeTimeframe]

def validate_start_end_timeframe(tf : WakatimeStartEndTimeframe) -> bool:
    try:
        datetime.strptime(tf.start, r"%Y-%m-%d")
        datetime.strptime(tf.end, r"%Y-%m-%d")
    except ValueError as _:
        return False
    else:
        return True

def validate_range_timeframe(tf : WakatimeRangeTimeframe) -> bool:
    is_valid = tf.range in (
        "Today",
        "Yesterday",
        "Last 7 Days",
        "Last 7 Days from Yesterday",
        "Last 14 Days",
        "Last 30 Days",
        "This Week",
        "Last Week", 
        "This Month",
        "Last Month"
    )

    return is_valid

def validate_timeframe(tf : WakatimeTimeframeType) -> None:

    if isinstance(tf, WakatimeRangeTimeframe):
        if not validate_range_timeframe(tf):
            raise InvalidTimeframeValue()
        
    elif isinstance(tf, WakatimeStartEndTimeframe):
        if not validate_start_end_timeframe(tf):
            raise InvalidTimeframeValue()
        
    else:
        raise InvalidTimeframeValue

__all__ = ["WakatimeTokens", "WakatimeAPIResponseIsNone", "WakatimeAPIResponse"]
