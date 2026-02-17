from fastapi.routing import APIRouter
from fastapi import HTTPException, Query
from typing import Annotated
import aiohttp
from urllib.parse import parse_qs
from uuid import UUID
from datetime import datetime
import jwt as pyjwt

from ..db.models import User, OAuth2Credentials
from ..db import get_session as get_db_session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..models import users as user_models

from ..utils.env import get_required_env

router = APIRouter()

@router.post("/login", tags=["auth"])
async def post_user_login(
    code : Annotated[str, Query(description="The code retrieved from an OAuth2 provider to be exchanged for access/refresh tokens")]
    ) -> user_models.LoginResponse:
    """
    Logs a user in using the code retrieved from the first step of the OAuth2 flow.
    This endpoint returns a JWT that can be used to authenticate the user into CodeCrunchr
    """

    # We need the code! We NEED it. Like, it's NOT optional????
    if not code:
        raise HTTPException(status_code=400, detail="code needed.")

    # Build the payload that we need to send to wakatime to get
    # the access/refresh tokens
    token_req_payload = {
        "client_id" : get_required_env("WAKA_APP_ID"),
        "client_secret" : get_required_env("WAKA_APP_SECRET"),
        "redirect_uri" : get_required_env("WAKA_REDIRECT_URI"),
        "grant_type" : "authorization_code",
        "code" : code
    }

    # Send that payload and get a response
    async with aiohttp.ClientSession() as session:
        async with session.post("https://wakatime.com/oauth/token", data=token_req_payload) as resp:

            # If we get something greater than a redirect or an okay, then we got an error
            # let the user know, because I don't know what would happen here if it was not okay
            if resp.status >= 400:
                raise HTTPException(status_code=500, detail="Failed to get tokens")

            # We get the raw text response here because it returns a horrible url-encoded form data
            # string that we need to parse :/
            raw_text_resp = await resp.text()
    
    # Using parse_qs, we get a dict where the values are arrays of the values we actually want.
    parsed_text_resp = parse_qs(raw_text_resp)

    # This is all the data we actually want
    user_uuid = UUID(parsed_text_resp["uid"][0])
    access_token = parsed_text_resp["access_token"][0]
    refresh_token = parsed_text_resp["refresh_token"][0]
    expires_at = datetime.fromisoformat(parsed_text_resp["expires_at"][0]).replace(tzinfo=None)

    # Now we need to check and see if there's already a user that matches `user_uuid` in our db.
    async with get_db_session() as session:
        matched_users = await session.scalar(select(User).where(User.id == user_uuid))

        # If we cannot find any users that match the user_uuid, then we must have a new user!
        if matched_users is None:
            session.add(User(id=user_uuid))

        # Prepare a statement to insert the new values into the oauth table
        stmt = (insert(OAuth2Credentials)
                .values(
                    user_id = user_uuid,
                    provider = "wakatime",
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    updated_at=datetime.now().replace(tzinfo=None)
                ))

        # When we execute this, we're running an `ON CONFLICT DO UPDATE` thing
        # which will update the access_token/refresh_token/expires_at if the user
        # already had a record in the table for the provider (wakatime)
        await session.execute(
            stmt.on_conflict_do_update(
                    constraint="pk_provider_per_user",
                    set_={
                        "access_token" : stmt.excluded.access_token,
                        "refresh_token" : stmt.excluded.refresh_token,
                        "expires_at" : stmt.excluded.expires_at,
                        "updated_at" : stmt.excluded.updated_at
                    }
                )
        )

        # We've made sure our user exists, and our credentials are updated
        # Lets get out of john and commit ts twin         
        await session.commit()

    # Now it's JWT time...

    # This is the payload, it just holds data that tells us who our user is.
    token_payload = {
        "user_id" : str(user_uuid)
    }

    # We then use the secret key defined in env to encode the payload and attach
    # a signature to it that we validate in our custom authn middleware.
    # NOTE: The token payload is NOT "encrypted", so don't slap random secret junk in there
    #       because we only really use an attached header signature thingy to validate the
    #       origin of the token
    token = pyjwt.encode(
        payload=token_payload,
        key=get_required_env("JWT_SECRET"),
        algorithm="HS256"
    )

    # Return the auth token that the user can now use to login to the stuff they need to
    return user_models.LoginResponse(
        token = token
    )

@router.post("/logout", tags=["auth"])
async def post_user_logout():
    pass

@router.post("/revoke_token", tags=["auth"])
async def post_user_revoke_token():
    pass

@router.get("/user/{user_id}", tags=["users"])
async def get_user_user():
    pass

@router.delete("/user", tags=["users"])
async def delete_user_user():
    pass

__all__ = [
    "router"
]