from typing import TypedDict, Generic, TypeVar

from ..utils.env import get_required_env

WAKA_CLIENT_ID = get_required_env("WAKA_APP_ID")
WAKA_CLIENT_SECRET = get_required_env("WAKA_APP_SECRET")
WAKA_REDIRECT_URI = get_required_env("WAKA_REDIRECT_URI")

# Token dict


class WakatimeTokens(TypedDict):
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


__all__ = ["WakatimeTokens", "WakatimeAPIResponseIsNone", "WakatimeAPIResponse"]
