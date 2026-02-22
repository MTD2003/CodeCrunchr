from datetime import datetime, timedelta

from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID
import jwt as pyjwt

from sqlalchemy import select

from ..db.models import User, WakatimeUserProfile
from ..db.helpers import update_oauth_tokens, recache_wakatime_profile
from ..db import get_session as get_db_session

from ..models import users as user_models

from ..utils.env import get_required_env

from ..dependencies.auth import get_current_user_wakatime_tokens
from ..wakatime import WakatimeTokens
from ..wakatime.auth import get_access_tokens
from ..wakatime.user import get_current_user

router = APIRouter()

RECACHE_OLD_WAKA_PROFILE_AFTER = timedelta(minutes=10)

@router.post("/login", tags=["auth"])
async def post_user_login(
    code: Annotated[
        str,
        Query(
            description="The code retrieved from an OAuth2 provider to be exchanged for access/refresh tokens"
        ),
    ],
) -> user_models.LoginResponse:
    """
    Logs a user in using the code retrieved from the first step of the OAuth2 flow.
    This endpoint returns a JWT that can be used to authenticate the user into CodeCrunchr
    """

    # We need the code! We NEED it. Like, it's NOT optional????
    if not code:
        raise HTTPException(status_code=400, detail="code needed.")

    wrapped_token_resp = await get_access_tokens(oauth_code=code)

    if wrapped_token_resp.status_code >= 300:
        raise HTTPException(status_code=400, detail="Failed to get tokens")

    token_resp = wrapped_token_resp.unwrap()

    # Now we need to check and see if there's already a user that matches `user_uuid` in our db.
    async with get_db_session() as session:
        matched_users = await session.scalar(
            select(User).where(User.id == token_resp["user_id"])
        )

        # If we cannot find any users that match the user_uuid, then we must have a new user!
        if matched_users is None:
            session.add(User(id=token_resp["user_id"]))

        # Update the user's oauth tokens with the new ones we just got
        # (This function will insert them if they don't already exist)
        await update_oauth_tokens(
            session=session,
            user_id=token_resp["user_id"],
            access_token=token_resp["access_token"],
            refresh_token=token_resp["refresh_token"],
            expires_at=token_resp["expires_at"],
            skip_encryption=False,
        )

        # We've made sure our user exists, and our credentials are updated
        # Lets get out of john and commit ts twin
        await session.commit()

    # Now it's JWT time...

    # This is the payload, it just holds data that tells us who our user is.
    token_payload = {"user_id": str(token_resp["user_id"])}

    # We then use the secret key defined in env to encode the payload and attach
    # a signature to it that we validate in our custom authn middleware.
    # NOTE: The token payload is NOT "encrypted", so don't slap random secret junk in there
    #       because we only really use an attached header signature thingy to validate the
    #       origin of the token
    token = pyjwt.encode(
        payload=token_payload, key=get_required_env("JWT_SECRET"), algorithm="HS256"
    )

    # Return the auth token that the user can now use to login to the stuff they need to
    return user_models.LoginResponse(token=token)


@router.post("/revoke_token", tags=["auth"])
async def post_user_revoke_token():
    pass


@router.get("/user", tags=["users"], name="Get current user profile")
async def get_current_user_profile(
    tokens: Annotated[WakatimeTokens, Depends(get_current_user_wakatime_tokens)],
) -> user_models.UserProfileResponse:
    """
    Returns the current user's profile.
    """
    
    # First we need to check and see whether or not the user has already been cached
    stmt = select(WakatimeUserProfile).where(WakatimeUserProfile.user_id == tokens['user_id'])
    
    async with get_db_session() as session:
        # `resp` now holds the currently cached data (if any) 
        resp = await session.scalar(stmt)

        # If there is no cached data, or the cached data is old, then recache the data
        if resp is None or resp.last_cached_at + RECACHE_OLD_WAKA_PROFILE_AFTER <= datetime.now():
            
            # This function returns the newly created instance of `WakatimeUserProfile`
            resp = await recache_wakatime_profile(session, tokens, "current")
            
            # Save after the recache 
            await session.commit()

        # At this point, we know we have an up-to-date WakatimeUserProfile instance.
        return user_models.UserProfileResponse(
            user_id = str(resp.user_id),
            wakatime = user_models.WakatimeProfile(
                user_id=str(resp.user_id),
                display_name=resp.display_name,
                full_name=resp.full_name,
                username=resp.username,
                photo_url=resp.photo_url,
                is_photo_public=resp.is_photo_public,
                last_cached_at=resp.last_cached_at,
            )
        )


@router.get("/user/{user_id}", tags=["users"])
async def get_user_user(
    tokens: Annotated[WakatimeTokens, Depends(get_current_user_wakatime_tokens)],
    user_id : UUID
) -> user_models.UserProfileResponse:
    """
    Returns the provided user's profile.

    Caveat: They need to have an account with our service in order for us to
    do a request to query their data. For privacy's sake
    """
    codecrunchr_user_stmt = select(User).where(User.id == user_id)
    waka_profile_stmt = select(WakatimeUserProfile).where(WakatimeUserProfile.user_id == user_id)

    async with get_db_session() as session:
        
        # Try to fetch the user
        user = await session.scalar(codecrunchr_user_stmt)

        # If we fail to find a user with the provided UUID, then raise a 404
        if user is None:
            raise HTTPException(
                status_code=404,
                detail=f"User with id `{user_id}` not found on CodeCrunchr"
            )

        # At this point, we know we have a valid user
        # We then copy the same protocol as the get_current_user_profile() func
        waka_profile = await session.scalar(waka_profile_stmt)

        # If there is no cached data, or the cached data is old, then recache the data
        if waka_profile is None or waka_profile.last_cached_at + RECACHE_OLD_WAKA_PROFILE_AFTER <= datetime.now():
            
            # This function returns the newly created instance of `WakatimeUserProfile`
            waka_profile = await recache_wakatime_profile(session, tokens, "current")
            
            # Save after the recache 
            await session.commit()

        # At this point, we know we have an up-to-date WakatimeUserProfile instance.
        return user_models.UserProfileResponse(
            user_id = str(waka_profile.user_id),
            wakatime = user_models.WakatimeProfile(
                user_id=str(waka_profile.user_id),
                display_name=waka_profile.display_name,
                full_name=waka_profile.full_name,
                username=waka_profile.username,
                photo_url=waka_profile.photo_url,
                is_photo_public=waka_profile.is_photo_public,
                last_cached_at=waka_profile.last_cached_at,
            )
        )


@router.delete("/user", tags=["users"])
async def delete_user_user():
    pass


__all__ = ["router"]
