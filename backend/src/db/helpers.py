from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from ..utils import tokens as tokens_utils
from ..db.models import OAuth2Credentials

OAUTH_EARLY_EXPIRY_DELTA = timedelta(minutes=5)


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


async def is_oauth_expired(
    creds: OAuth2Credentials, *, pos_offset: timedelta = OAUTH_EARLY_EXPIRY_DELTA
) -> bool:
    return creds.expires_at >= (datetime.now() + pos_offset)


__all__ = ["is_oauth_expired", "update_oauth_tokens"]
