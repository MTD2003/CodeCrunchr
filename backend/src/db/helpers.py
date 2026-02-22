from datetime import datetime, timedelta
from typing import Literal, Union
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from logging import getLogger

from ..wakatime import WakatimeTokens
from ..wakatime import user as waka_user_funcs
from ..utils import tokens as tokens_utils
from ..db.models import OAuth2Credentials, WakatimeUserProfile

OAUTH_EARLY_EXPIRY_DELTA = timedelta(minutes=5)
LOGGER = getLogger(__name__)

async def update_oauth_tokens(
    session: AsyncSession,
    user_id: UUID,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    *,
    skip_encryption: bool = False,
) -> None:
    # Encrypt the provided tokens if we haven't already
    if not skip_encryption:
        access_token = tokens_utils.encrypt(access_token)
        refresh_token = tokens_utils.encrypt(refresh_token)

    LOGGER.debug(f"Pushing new access/refresh credentials to db for user: {user_id}")

    # Prepare a statement to insert the new values into the oauth table
    stmt = insert(OAuth2Credentials).values(
        user_id=user_id,
        provider="wakatime",
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        updated_at=datetime.now().replace(tzinfo=None),
    )

    # When we execute this, we're running an `ON CONFLICT DO UPDATE` thing
    # which will update the access_token/refresh_token/expires_at if the user
    # already had a record in the table for the provider (wakatime)
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="pk_provider_per_user",
            set_={
                "access_token": stmt.excluded.access_token,
                "refresh_token": stmt.excluded.refresh_token,
                "expires_at": stmt.excluded.expires_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
    )


def is_oauth_expired(
    creds: OAuth2Credentials, *, pos_offset: timedelta = OAUTH_EARLY_EXPIRY_DELTA
) -> bool:
    is_expired = creds.expires_at < (datetime.now() + pos_offset)

    LOGGER.debug(f"Check for expired credentials for user id: {creds.user_id}, {is_expired=}")

    return is_expired


async def recache_wakatime_profile(
    session: AsyncSession,
    tokens : WakatimeTokens,
    user_id : Union[Literal["current"], UUID]
) -> WakatimeUserProfile:
    """
    Forces a recache for a user's wakatime profile.

    This function handles the database side and allat, but does not
    check to see if the profile is old, do that yourself.

    REMEMBER TO COMMIT AFTER THIS!!
    """

    # HACK: evil f**king wizard sh*t lol
    coro = waka_user_funcs.get_current_user(tokens) if user_id == "current" else waka_user_funcs.get_user(tokens, user_id)

    # We run the coroutine we got above to get a UserResponse
    user_resp = await coro

    # If we don't get a user, then the user must have provided an invalid id
    if user_resp is None:
        raise ValueError("Failed to recache wakatime profile: No user found on Wakatime matching the provided user_id")

    # Get the current user's token, because if `user_id` provided was "current",
    # then the validation for the following function fails because "current" isn't
    # a UUID... bruh.
    current_users_token = tokens["user_id"]

    # This is the base insert statement...
    insert_statement = insert(WakatimeUserProfile).values(
        dict(
            user_id = user_resp.id,
            display_name = user_resp.display_name,
            full_name = user_resp.full_name,
            username = user_resp.username,
            photo_url = user_resp.photo,
            is_photo_public = user_resp.is_photo_public,
            email = user_resp.email,
            timezone = user_resp.timezone,
            last_cached_at = datetime.now(tz=None)
        )
    )

    # ... To which we add on an on_conflict_do_update clause to handle updating the
    # row in the case where the user *has* had their data pulled previously.
    # They are seperated because we need `insert_statement.excluded` to find what columns
    # in the record need updating.
    insert_statement_with_conflict_clause = (
        insert_statement
            .on_conflict_do_update(set_=insert_statement.excluded, index_elements=[WakatimeUserProfile.user_id])
            .returning(WakatimeUserProfile)
        )

    # Run that statement we just built.
    new_profile = await session.scalar(insert_statement_with_conflict_clause)

    # This shouldn't happen
    if new_profile is None:
        raise Exception("Something went wrong")

    LOGGER.debug(f"User with id: {user_id} ({user_resp.display_name}) had their wakatime profile recached!")

    # Return that new profile
    return new_profile


__all__ = ["is_oauth_expired", "update_oauth_tokens"]
