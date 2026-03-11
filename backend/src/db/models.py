from sqlalchemy import (
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from uuid import UUID
from sqlalchemy import func as db_funcs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from datetime import datetime, date


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
    preferences = relationship(
        "UserPreferences", back_populates="user", cascade="all, delete-orphan"
    )
    credentials = relationship(
        "OAuth2Credentials", back_populates="user", cascade="all, delete-orphan"
    )
    wakatime_profile = relationship(
        "WakatimeUserProfile", back_populates="user", cascade="all, delete-orphan"
    )
    wakatime_durations = relationship(
        "WakatimeDuration", back_populates="user", cascade="all, delete-orphan"
    )


class UserPreferences(CodeCrunchrBase):
    """
    Contains JSON data for a user's preferences
    """

    __tablename__ = "codecrunchr_user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("codecrunchr_users.id", ondelete="CASCADE"), primary_key=True
    )

    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=db_funcs.now()
    )

    preferences: Mapped[dict] = mapped_column(postgresql.JSONB, server_default="'{}'")

    user = relationship("User", back_populates="preferences")


class OAuth2Credentials(CodeCrunchrBase):
    """
    Responsible for holding the OAuth2 credentials for the user
    """

    __tablename__ = "codecrunchr_oauth"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("codecrunchr_users.id", ondelete="CASCADE")
    )

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


class WakatimeUserProfile(CodeCrunchrBase):
    """
    Responsible for holding information about the user's wakatime account
    """

    __tablename__ = "codecrunchr_waka_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("codecrunchr_users.id", ondelete="CASCADE"), primary_key=True
    )
    user = relationship("User", back_populates="wakatime_profile")

    # The user's display name on wakatime
    # Could be `full_name`, could be @username, who knows!
    display_name: Mapped[str]

    # The user's full name
    full_name: Mapped[str]

    # The user's @username handle on wakatime
    username: Mapped[str]

    # A url pointing the the user's profile photo on wakatime
    photo_url: Mapped[str]

    # Whether or not the user publicly shows their photo on wakatime
    # (We should respect this)
    is_photo_public: Mapped[bool]

    email: Mapped[str]

    # Could be useful, in America/Halifax format I believe
    timezone: Mapped[str]

    last_cached_at: Mapped[datetime] = mapped_column(server_default=db_funcs.now())


class WakatimeDuration(CodeCrunchrBase):
    """
    Responsible for holding the cumulative duration data
    """

    __tablename__ = "codecrunchr_wakatime_durations"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("codecrunchr_users.id", ondelete="CASCADE")
    )
    user = relationship("User", back_populates="wakatime_durations")

    date: Mapped["date"]

    total_seconds: Mapped[float]

    last_cached_at: Mapped[datetime] = mapped_column(server_default=db_funcs.now())

    languages: Mapped[list["WakatimeLanguageDuration"]] = relationship(
        "WakatimeLanguageDuration",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("user_id", "date", name="unique_date_user_id"),)


class WakatimeLanguageDuration(CodeCrunchrBase):
    """
    Responsible for holding an individual language breakdown for a duration
    record.

    The aggregation of all language durations total_seconds should equal the
    parent duration's total_seconds.
    """

    __tablename__ = "codecrunchr_wakatime_language_durations"

    parent_id: Mapped[int] = mapped_column(
        ForeignKey("codecrunchr_wakatime_durations.id", ondelete="CASCADE")
    )
    parent = relationship("WakatimeDuration", back_populates="languages")

    language: Mapped[str]

    total_seconds: Mapped[float]

    __table_args__ = (
        PrimaryKeyConstraint("parent_id", "language", name="pk_parent_id_language"),
    )


class WeeklyLeaderboard(CodeCrunchrBase):
    """
    Responsible for holding a snapshot of the coding time
    leaderboard for the week.
    """

    __tablename__ = "codecrunchr_weekly_leaderboard"

    week_start: Mapped[date] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    total: Mapped[float] = mapped_column(nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (Index("idx_week_start_rank", "week_start", "rank"),)


__all__ = [
    "CodeCrunchrBase",
    "User",
    "UserPreferences",
    "OAuth2Credentials",
    "WakatimeUserProfile",
]
