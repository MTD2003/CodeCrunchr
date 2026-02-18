from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID
import jwt as pyjwt

from sqlalchemy import select

from ..db.models import User
from ..db.helpers import update_oauth_tokens
from ..db import get_session as get_db_session

from ..models import users as user_models

from ..utils.env import get_required_env

from ..dependencies.auth import get_current_user_id
from ..wakatime.auth import get_access_tokens

router = APIRouter()


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


@router.get("/user", tags=["user"], name="Get current user profile")
async def get_current_user_profile(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    # HACK: Just to prove that auth is working to some capacity
    return f"{user_id=}"


@router.get("/user/{user_id}", tags=["users"])
async def get_user_user():
    pass


@router.delete("/user", tags=["users"])
async def delete_user_user():
    pass


__all__ = ["router"]
