from datetime import datetime
import aiohttp
from urllib.parse import parse_qs
from uuid import UUID
from typing import TypedDict

from . import (
    WAKA_CLIENT_SECRET,
    WAKA_CLIENT_ID,
    WAKA_REDIRECT_URI,
    WakatimeAPIResponse,
)


class AccessTokensResponse(TypedDict):
    user_id: UUID
    access_token: str
    refresh_token: str
    expires_at: datetime


async def get_access_tokens(
    oauth_code: str,
) -> WakatimeAPIResponse[AccessTokensResponse]:
    async with aiohttp.ClientSession() as cs:
        async with cs.post(
            "https://wakatime.com/oauth/token",
            data={
                "client_id": WAKA_CLIENT_ID,
                "client_secret": WAKA_CLIENT_SECRET,
                "redirect_uri": WAKA_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code": oauth_code,
            },
        ) as resp:
            resp_status = resp.status
            raw_resp_text = await resp.text()

    parsed_text_resp = parse_qs(raw_resp_text)

    response_object = AccessTokensResponse(
        user_id=UUID(parsed_text_resp["uid"][0]),
        access_token=parsed_text_resp["access_token"][0],
        refresh_token=parsed_text_resp["refresh_token"][0],
        expires_at=datetime.fromisoformat(parsed_text_resp["expires_at"][0]).replace(
            tzinfo=None
        ),
    )

    return WakatimeAPIResponse(
        status_code=resp_status,
        response=response_object,
    )


async def refresh_access_token(
    refresh_token: str,
) -> WakatimeAPIResponse[AccessTokensResponse]:
    async with aiohttp.ClientSession() as cs:
        async with cs.post(
            "https://wakatime.com/oauth/token",
            data={
                "client_id": WAKA_CLIENT_ID,
                "client_secret": WAKA_CLIENT_SECRET,
                "redirect_uri": WAKA_REDIRECT_URI,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        ) as resp:
            resp_status = resp.status
            raw_resp_text = await resp.text()

    parsed_text_resp = parse_qs(raw_resp_text)

    response_object = AccessTokensResponse(
        user_id=UUID(parsed_text_resp["uid"][0]),
        access_token=parsed_text_resp["access_token"][0],
        refresh_token=parsed_text_resp["refresh_token"][0],
        expires_at=datetime.fromisoformat(parsed_text_resp["expires_at"][0]).replace(
            tzinfo=None
        ),
    )

    return WakatimeAPIResponse(
        status_code=resp_status,
        response=response_object,
    )


# TODO
async def revoke_token(token: str) -> None:
    raise NotImplementedError()


# TODO
async def revoke_tokens_for_user(user_id: UUID) -> None:
    raise NotImplementedError()
