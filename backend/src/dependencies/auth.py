from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
from typing import Annotated, TypedDict
from uuid import UUID
import jwt as pyjwt

from sqlalchemy import select

from ..caching import Cache
from ..utils.env import get_required_env
from ..utils import tokens as tokens_utils
from ..db.models import OAuth2Credentials
from ..db.helpers import is_oauth_expired, OAUTH_EARLY_EXPIRY_DELTA, update_oauth_tokens
from ..db import get_session as get_db_session

from ..wakatime import WakatimeTokens
from ..wakatime.auth import refresh_access_token

# ========== HEADER DEF. ==========

BEARER_SCHEME = HTTPBearer()

# ========== CACHE STUFF ==========


USER_ID_CACHE: Cache[UUID] = Cache()
WAKATIME_TOKEN_CACHE: Cache[WakatimeTokens] = Cache()


def clear_caches_for_token(jwt_token: str) -> None:
    """
    Removes any instance of the provided JWT from the auth caches
    """
    USER_ID_CACHE.remove(jwt_token)
    WAKATIME_TOKEN_CACHE.remove(jwt_token)


# ========== SHARED FUNCTIONS ==========


class CodeCrunchrJWTPayload(TypedDict):
    user_id: str


def decode_jwt_payload(jwt_token: str) -> CodeCrunchrJWTPayload:
    # Decode the payload _AND VERIFY_ that the token came from our login procedure.
    try:
        decoded_payload = pyjwt.decode(
            jwt_token,
            key=get_required_env("JWT_SECRET"),
            algorithms="HS256",
            verify=True,
        )
    except Exception as _:
        raise HTTPException(status_code=400, detail="Invalid JWT provided")

    return CodeCrunchrJWTPayload(user_id=decoded_payload["user_id"])


# ========== DEPENDENCIES ==========


async def get_current_user_id(
    token: "AuthHeaderDependencyType",
) -> UUID:
    """
    Gets the current user's id from the token provided in the authorization header.
    """

    # I hate this.
    global USER_ID_CACHE

    # Extract the JWT from the header
    jwt_token = token.credentials

    # Check to see if we already have the jwt cached to avoid extra work
    cached_id = USER_ID_CACHE.get(jwt_token)

    if cached_id:
        return cached_id

    decoded_payload = decode_jwt_payload(jwt_token)
    user_id = UUID(decoded_payload["user_id"])

    # TODO: Caches should expire
    USER_ID_CACHE.add(key=jwt_token, item=user_id, expires_at=None)

    return user_id


async def get_current_user_wakatime_tokens(
    token: "AuthHeaderDependencyType",
) -> WakatimeTokens:
    # I hate this too.
    global WAKATIME_TOKEN_CACHE

    # Get the jwt token
    jwt_token = token.credentials

    # Check cache...
    cached_wakatime_tokens = WAKATIME_TOKEN_CACHE.get(jwt_token)

    # Cache hit? return that
    if cached_wakatime_tokens:
        return cached_wakatime_tokens

    # No cache? decode payload and get user id
    decoded_payload = decode_jwt_payload(jwt_token)
    user_id = UUID(decoded_payload["user_id"])

    # Look for OAuth2Credentials attached to this user id
    stmt = select(OAuth2Credentials).where(OAuth2Credentials.user_id == user_id)

    async with get_db_session() as session:
        creds_resp = await session.scalar(stmt)

        # If the user does not have credentials, then throw an error.
        # (This should never happen)
        if creds_resp is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to get wakatime credentials, please relog?",
            )

        # Decrypt the access token and refresh token
        decrypted_access_token = tokens_utils.decrypt(creds_resp.access_token)
        decrypted_refresh_token = tokens_utils.decrypt(creds_resp.refresh_token)

        # If the access token is expired, refresh it.
        if is_oauth_expired(creds_resp):
            new_tokens = await refresh_access_token(creds_resp.refresh_token)

            if new_tokens.status_code >= 300:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to validate tokens, please log back in!",
                )

            decrypted_access_token = new_tokens.unwrap()["access_token"]
            decrypted_refresh_token = new_tokens.unwrap()["refresh_token"]

            await update_oauth_tokens(
                session=session,
                user_id=user_id,
                access_token=decrypted_access_token,
                refresh_token=decrypted_refresh_token,
                expires_at=new_tokens.unwrap()["expires_at"],
                skip_encryption=False,
            )

            await session.commit()

    # Create a dict containing both tokens
    tokens_obj = WakatimeTokens(
        user_id=user_id,
        access_token=decrypted_access_token,
        refresh_token=decrypted_refresh_token,
    )

    # Add the dict to the cache so we don't have to do all this
    # rigamaroll again to get it
    WAKATIME_TOKEN_CACHE.add(
        jwt_token,
        tokens_obj,
        expires_at=(creds_resp.expires_at - OAUTH_EARLY_EXPIRY_DELTA),
    )

    # return those sweet juicy decrypted tokens
    return tokens_obj


# ========== DEPENDENCY TYPES ==========

AuthHeaderDependencyType = Annotated[
    HTTPAuthorizationCredentials, Depends(BEARER_SCHEME)
]
TokenDependencyType = Annotated[
    WakatimeTokens, Depends(get_current_user_wakatime_tokens)
]
UserIDDependencyType = Annotated[UUID, Depends(get_current_user_id)]
