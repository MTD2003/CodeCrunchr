from sqlalchemy import ForeignKey, PrimaryKeyConstraint, DateTime
from sqlalchemy.dialects import postgresql
from uuid import UUID
from sqlalchemy import func as db_funcs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from datetime import datetime


class CodeCrunchrBase(DeclarativeBase):
    pass


class User(CodeCrunchrBase):
    """
    You will never guess what this is responsible for.
    """

    __tablename__ = "codecrunchr_users"

    id: Mapped[UUID] = mapped_column(postgresql.UUID, primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=db_funcs.now()
    )

    # Relationships with other models
    preference_overrides = relationship("UserPreferenceOverride", back_populates="user")
    credentials = relationship("OAuth2Credentials", back_populates="user")


class UserPreferenceOverride(CodeCrunchrBase):
    """
    Responsible for holding the overrides (the differences) on the default
    preference config for each individual user.

    1 record = 1 preference value change
    """

    __tablename__ = "codecrunchr_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("codecrunchr_users.id"))

    # Preference identifier
    slug: Mapped[str]

    # Overriden value
    value: Mapped[str]

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=db_funcs.now()
    )

    # Relationships
    user = relationship("User", back_populates="preference_overrides")

    # A user should only ever have one slug in their pocket...
    # (Actually meant to prevent users from having duplicate preference overrides)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "slug", name="pk_preference_slug_per_user"),
    )


class OAuth2Credentials(CodeCrunchrBase):
    """
    Responsible for holding the OAuth2 credentials for the user
    """

    __tablename__ = "codecrunchr_oauth"

    user_id = mapped_column(ForeignKey("codecrunchr_users.id"))

    # The OAuth2 provider we got the credentials from
    provider: Mapped[str] = mapped_column(nullable=False)

    # The access token and refresh token we have
    access_token: Mapped[str] = mapped_column(nullable=False)
    refresh_token: Mapped[str] = mapped_column(nullable=False)

    # When the access_token expires
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    # When this record was created/updated (in the event of an access_token expiring)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=db_funcs.now(),
    )

    # Relationships
    user = relationship("User", back_populates="credentials")

    # A user should only ever have credentials for one provider (e.g., Wakatime)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "provider", name="pk_provider_per_user"),
    )


__all__ = ["CodeCrunchrBase", "User", "UserPreferenceOverride", "OAuth2Credentials"]
