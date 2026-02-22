from datetime import datetime

from pydantic import BaseModel


class LoginResponse(BaseModel):
    """
    A response that holds a JWT token for authentication
    in CodeCrunchr
    """

    token: str


class WakatimeProfile(BaseModel):
    user_id: str

    display_name: str
    full_name: str
    username: str

    photo_url: str
    is_photo_public: bool

    last_cached_at: datetime


class UserProfileResponse(BaseModel):
    user_id: str

    # In the future, this *could* be null.
    wakatime: WakatimeProfile


__all__ = ["LoginResponse"]
