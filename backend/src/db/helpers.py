from datetime import datetime, timedelta, date
from typing import AsyncGenerator, Literal, Union
from uuid import UUID
from sqlalchemy import and_, or_, select, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import joinedload
from sqlalchemy import func as db_funcs
from logging import getLogger

from ..wakatime import (
    WakatimeStartEndTimeframe,
    WakatimeRangeTimeframe,
    WakatimeTokens,
    WakatimeTimeframeType,
)
from ..wakatime import user as waka_user_funcs
from ..wakatime import summaries
from ..utils import tokens as tokens_utils
from ..db.models import (
    OAuth2Credentials,
    WakatimeUserProfile,
    WakatimeDuration,
    WakatimeLanguageDuration,
)

OAUTH_EARLY_EXPIRY_DELTA = timedelta(minutes=5)
DEFAULT_DURATION_REFRESH_THRESHOLD = timedelta(minutes=10)

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

    LOGGER.debug(
        f"Check for expired credentials for user id: {creds.user_id}, {is_expired=}"
    )

    return is_expired


async def recache_wakatime_profile(
    session: AsyncSession,
    tokens: WakatimeTokens,
    user_id: Union[Literal["current"], UUID],
) -> WakatimeUserProfile:
    """
    Forces a recache for a user's wakatime profile.

    This function handles the database side and allat, but does not
    check to see if the profile is old, do that yourself.

    REMEMBER TO COMMIT AFTER THIS!!
    """

    # HACK: evil f**king wizard sh*t lol
    coro = (
        waka_user_funcs.get_current_user(tokens)
        if user_id == "current"
        else waka_user_funcs.get_user(tokens, user_id)
    )

    # We run the coroutine we got above to get a UserResponse
    user_resp = await coro

    # If we don't get a user, then the user must have provided an invalid id
    if user_resp is None:
        raise ValueError(
            "Failed to recache wakatime profile: No user found on Wakatime matching the provided user_id"
        )

    # This is the base insert statement...
    insert_statement = insert(WakatimeUserProfile).values(
        dict(
            user_id=user_resp.id,
            display_name=user_resp.display_name,
            full_name=user_resp.full_name,
            username=user_resp.username,
            photo_url=user_resp.photo,
            is_photo_public=user_resp.is_photo_public,
            email=user_resp.email,
            timezone=user_resp.timezone,
            last_cached_at=datetime.now(tz=None),
        )
    )

    # ... To which we add on an on_conflict_do_update clause to handle updating the
    # row in the case where the user *has* had their data pulled previously.
    # They are seperated because we need `insert_statement.excluded` to find what columns
    # in the record need updating.
    insert_statement_with_conflict_clause = insert_statement.on_conflict_do_update(
        set_=insert_statement.excluded, index_elements=[WakatimeUserProfile.user_id]
    ).returning(WakatimeUserProfile)

    # Run that statement we just built.
    new_profile = await session.scalar(insert_statement_with_conflict_clause)

    # This shouldn't happen
    if new_profile is None:
        raise Exception("Something went wrong")

    LOGGER.debug(
        f"User with id: {user_id} ({user_resp.display_name}) had their wakatime profile recached!"
    )

    # Return that new profile
    return new_profile


async def force_oauth_tokens_to_expire(
    session: AsyncSession, user_id: UUID, provider: str = "wakatime"
) -> None:
    """
    Forces OAuth2 tokens to expire in the database for the provided user id.

    REMEMBER TO COMMIT!
    """

    stmt = (
        select(OAuth2Credentials)
        .where(OAuth2Credentials.provider == provider)
        .where(OAuth2Credentials.user_id == user_id)
    )

    user = await session.scalar(stmt)

    if user is None:
        raise ValueError("Cannot force expire oauth: invalid user_id or provider")

    # Setting user to datetime.min will ensure that the service sees the tokens as expired
    user.expires_at = datetime.min


async def update_user_durations(
    session: AsyncSession,
    tokens: WakatimeTokens,
    summary: summaries.SummaryResponseModel,
):
    """
    Pushes the summary data provided into the database for the provided user
    """

    # Get the start and end dates for the provided summary
    start_date = datetime.strptime(summary.start, r"%Y-%m-%dT%H:%M:%SZ").date()
    end_date = datetime.strptime(summary.end, r"%Y-%m-%dT%H:%M:%SZ").date()

    # Get the number of days between the days
    date_diff = end_date - start_date

    # Then, generate an array of date objects
    days = [start_date + (timedelta(days=1) * n) for n in range(date_diff.days)]

    # Then using that array of sorted date objects, and the sorted summary data,
    # we zip() then, and iterate through them to build out the values for the
    # top-most coding time duration model
    duration_data = [
        dict(
            user_id=tokens["user_id"],
            date=duration_date,
            total_seconds=duration.grand_total.total_seconds,
            last_cached_at=datetime.now(tz=None),
        )
        for duration_date, duration in zip(days, summary.data)
    ]

    duration_insert_stmt = insert(WakatimeDuration).values(duration_data)

    # Adding on a conflict statement to make sure that we can call this function even
    # if we already have data, we can just update it (this is important when the user
    # queries the data for "today", as it should be updated, not ignored :/)
    duration_insert_stmt_with_conflict = duration_insert_stmt.on_conflict_do_update(
        set_={
            "total_seconds": duration_insert_stmt.excluded.total_seconds,
            "last_cached_at": duration_insert_stmt.excluded.last_cached_at,
        },
        constraint="unique_date_user_id",
    ).returning(WakatimeDuration)

    # Get the new durations we just made, because we need the ids from them in order to assign the
    # languages to their associated parent durations
    new_durations = await session.scalars(duration_insert_stmt_with_conflict)
    new_durations_sorted_by_date = sorted(
        new_durations.all(), key=lambda d: d.date, reverse=False
    )

    LOGGER.info(
        f"Added new durations: {len(new_durations_sorted_by_date)} for user {tokens['user_id']}"
    )

    language_breakdowns = []

    for summary_section, duration_model in zip(
        summary.data, new_durations_sorted_by_date
    ):
        language_breakdowns.extend(
            [
                dict(
                    parent_id=duration_model.id,
                    language=lang.name,
                    total_seconds=lang.total_seconds,
                )
                for lang in summary_section.languages
            ]
        )

    language_insert_stmt = insert(WakatimeLanguageDuration).values(language_breakdowns)

    language_insert_stmt_with_conflict = language_insert_stmt.on_conflict_do_update(
        set_={
            "total_seconds": language_insert_stmt.excluded.total_seconds,
        },
        constraint="pk_parent_id_language",
    ).returning(WakatimeLanguageDuration)

    new_language_durations = (
        await session.scalars(language_insert_stmt_with_conflict)
    ).all()

    LOGGER.info(
        f"Added new language breakdowns: {len(new_language_durations)} for user {tokens['user_id']}"
    )

    # This nonsense takes the newly created and returned `WakatimeLanguageDuration` objects and
    # groups them based on their parent.
    languages_grouped_by_parent = {}
    for lang_duration in new_language_durations:
        pid = lang_duration.parent_id

        if pid not in languages_grouped_by_parent:
            languages_grouped_by_parent[pid] = []

        languages_grouped_by_parent[pid].append(lang_duration)

    # We use the grouped durations to propogate the "languages" relationship in the parent model,
    # which saves us manually querying the languages again for every single new parent duration
    # we just created (We literally just made the data, just return it lol)
    for duration in new_durations_sorted_by_date:
        set_committed_value(
            duration, "languages", languages_grouped_by_parent.get(duration.id, [])
        )

    # Now hopefully, SQLAlchemy's stupid lifetime bs with the sessions or whatever don't completely
    # mangle the new durations I'm returning, just let me use them PLEASE
    return new_durations_sorted_by_date


DurationRecacheType = tuple[date, date] | None


async def get_cached_user_durations(
    session: AsyncSession,
    user_id: UUID,
    duration_timeframe: WakatimeTimeframeType,
    *,
    eager_load: bool = False,
    today_refresh_threshold: timedelta | None = DEFAULT_DURATION_REFRESH_THRESHOLD,
) -> tuple[list[WakatimeDuration], DurationRecacheType]:

    # To keep the parameters easy to manage, providing None to the
    # `today_refresh_threshold` will set it to a zeroed timedelta.
    if today_refresh_threshold is None:
        today_refresh_threshold = timedelta(seconds=0)

    # First we need to get the proper statement for the `duration_timeframe` type that was provided
    if isinstance(duration_timeframe, WakatimeStartEndTimeframe):
        start_date = datetime.strptime(duration_timeframe.start, r"%Y-%m-%d").date()
        end_date = datetime.strptime(duration_timeframe.end, r"%Y-%m-%d").date()

        stmt = (
            select(WakatimeDuration)
            .where(WakatimeDuration.user_id == user_id)
            .where(WakatimeDuration.date >= start_date)
            .where(WakatimeDuration.date <= end_date)
            .order_by(asc(WakatimeDuration.date))
        )

        # If the eager load kwarg is true then we also load `WakatimeDuration.languages` here
        if eager_load:
            stmt = stmt.options(joinedload(WakatimeDuration.languages))

    elif isinstance(duration_timeframe, WakatimeRangeTimeframe):
        # We probably will never use this function for this :/
        raise NotImplementedError(
            "Getting cached durations from `WakatimeRangeTimeframe` not supported."
        )

    else:
        raise ValueError(
            "Failed to get cached user durations: invalid duration timeframe provided"
        )

    duration_scalar = await session.scalars(stmt)
    durations = duration_scalar.unique().all()

    now = datetime.now(tz=None)
    today = now.date()
    durations_includes_today = start_date <= today and today <= end_date

    # Figure out the maximum number of days which we actually would need
    # to store for this range. We omit days which are past today.
    if end_date > today:
        max_day_count = (today - start_date).days + 1
    else:
        max_day_count = (end_date - start_date).days + 1

    # NOTE: I know, this is gross.
    # A tuple representing a bool (if a recache is needed), and a tuple
    # denoting the inclusive range of days (start/end)
    needs_recache = None

    # We need a recache if either:
    # * The number of days for which we have durations for does not match the number of
    #   durations we retrived, OR
    # * One of the durations we returned includes today
    if len(durations) < max_day_count or durations_includes_today:
        # We don't need to recache any day which we've already cached
        # UNLESS it is today, in which case we probably should get the up-to-date data.
        days_not_needing_recaching = {
            d.date
            for d in durations
            if d.date != today or (d.last_cached_at + today_refresh_threshold > now)
        }

        # This is probably incredibly inefficient
        days_needing_recaching = [
            start_date + timedelta(days=d)
            for d in range(max_day_count)
            if (start_date + timedelta(days=d)) not in days_not_needing_recaching
        ]

        LOGGER.debug(
            f"Days needing recaching: {len(days_needing_recaching)} vs not: {len(days_not_needing_recaching)}"
        )

        # Sanity check, we dont need to return a timeframe if there are no
        # days to recache in the array.
        if days_needing_recaching:
            # Get the min and max values for the dates which need recaching
            recache_start_date = min(days_needing_recaching)
            recache_end_date = max(days_needing_recaching)

            needs_recache = (recache_start_date, recache_end_date)

    return (list(durations), needs_recache)


# TODO: find a more appropriate name for this function
# It literally does so many things
async def evil_duration_fetching_function(
    session: AsyncSession,
    tokens: WakatimeTokens,
    timeframe: WakatimeStartEndTimeframe,
    *,
    today_refresh_threshold: timedelta | None = DEFAULT_DURATION_REFRESH_THRESHOLD,
) -> list[WakatimeDuration]:
    """
    This is the evil duration fetching function.

    It tries to fetch all the durations within the timeframe provided from
    the database. If it can't, it will try to query wakatime and stitch together
    what exists of the pre-existing duration data with the new duration data in
    order to fulfill the request of the timeframe provided.

    This function will also attempt to update "today" if it has not been refreshed
    in the last `today_refresh_threshold` delta.
    """

    # We gather what information we currently have in the database
    # This function also returns the smallest range of what we *don't* have
    cached_durations, needs_recache = await get_cached_user_durations(
        session=session,
        duration_timeframe=timeframe,
        user_id=tokens["user_id"],
        eager_load=True,
    )

    # If we don't need a recache, then we have all of the data.
    # We can just end the function here
    if needs_recache is None:
        return cached_durations

    LOGGER.debug(
        f"User {tokens['user_id']} needs recache of durations between {timeframe.start}-{timeframe.end}..."
    )

    # Unpack the tuple given to us when needs_recache is non-null.
    recache_start, recache_end = needs_recache

    # Then, take those values and pipe them into a timeframe object
    # to pass throughout other functions
    recache_timeframe = WakatimeStartEndTimeframe(
        start=recache_start.strftime(r"%Y-%m-%d"), end=recache_end.strftime(r"%Y-%m-%d")
    )

    # Now we grab all the durations within the recache timeframe,
    # this should "complete" the data for the originally requested
    # `timeframe`.
    new_summary_resp = await summaries.get_summaries(
        tokens=tokens, user="current", timeframe=recache_timeframe
    )

    # In the event that we get a non-OK status code from wakatime, we
    # should throw an exception and handle that elsewhere.
    if new_summary_resp.status_code != 200:
        raise ValueError("Failed to get durations")

    # Otherwise, we can continue by pushing the new durations into the
    # database.
    # NOTE: We can call ".unwrap()" here because if the status code was 200
    # then we must have a valid response.
    new_durations = await update_user_durations(
        session=session, tokens=tokens, summary=new_summary_resp.unwrap()
    )

    LOGGER.debug(
        f"Successfully recached {len(new_durations)} for user {tokens['user_id']}!"
    )

    today = date.today()

    # Now we need to build a complete replacement for `cached_durations`
    # incorporating the data from `new_durations` (ugh)
    tmp_cached_durations = []

    # Get the number of days that the original timeframe contains
    max_days_in_week = timeframe.get_days_inclusive()

    # If the timeframe includes today, that means we likely do not have a
    # full week's worth of data, so we need to figure out the difference
    # between the original timeframe's start and today (plus 1 to include today)
    if timeframe.includes_date(today):
        max_days_in_week = (today - timeframe.start_date).days + 1

    # This while-loop builds a new `cached_durations` by doing some weird
    # indexing nonsense and figuring out which date comes "next" while prioritizing
    # the new durations over the old
    # Assume:
    # * Xn == Yn == None is impossible
    # * Yn is always prioritized (most recent data)
    xn, yn = 0, 0
    while len(tmp_cached_durations) < max_days_in_week:
        # These should both be sorted.
        duration_y = new_durations[yn]
        duration_x = None if xn >= len(cached_durations) else cached_durations[xn]

        if duration_x is not None and duration_x.date < duration_y.date:
            xn += 1
            tmp_cached_durations.append(duration_x)
        else:
            yn += 1
            tmp_cached_durations.append(duration_y)

    # We return the newly built tmp_cached_durations
    return tmp_cached_durations


async def get_user_ids_with_incomplete_durations(
    session : AsyncSession,
    timeframe : WakatimeStartEndTimeframe,
    *,
    incomplete_today_check : bool = False,
    today_refresh_threshold: timedelta | None = DEFAULT_DURATION_REFRESH_THRESHOLD,
) -> list[UUID]:
    """
    Returns a list of all the user uuids which do not have complete
    duration data for the given start/end timeframe
    """

    where_clause = WakatimeDuration.date.between(timeframe.start_date, timeframe.end_date)

    # If we need to check if "today" is incomplete, we must first check that we actually need to... 
    # (tf includes today?)
    if incomplete_today_check and timeframe.includes_date(date.today()):

        # If it includes today, then we must only need to cache up to today,
        # so we modify the timeframe to reflect that
        timeframe = WakatimeStartEndTimeframe(
            start = timeframe.start_date.strftime(r"%Y-%m-%d"),
            end = date.today().strftime(r"%Y-%m-%d")
        )

        # We then modify the where_clause to include durations which:
        # 1. Are between the start and end dates (inclusive)
        # 2. Either isn't today or if it was today, was cached within 
        #    the threshold provided in args
        where_clause = and_(
            WakatimeDuration.date.between(timeframe.start_date, timeframe.end_date),
            or_(
                WakatimeDuration.date != timeframe.end_date,
                WakatimeDuration.last_cached_at + today_refresh_threshold > datetime.now(),
            )
        )

    # Get the number of days included within the timeframe
    timeframe_day_span = timeframe.get_days_inclusive()

    # The breakdown of this query goes as follows:
    # 1. Fetch the user ids ...
    # 2. Where the date is between the start and end timeframe dates ...
    # 3. Grouped by user ids (so we can perform an aggregate function) ...
    # 4. Where a user_id is associated with less than the required number 
    #    of days within the provided timeframe. (count() is the agg. func.)
    stmt = (
        select(WakatimeDuration.user_id)
            .where(where_clause)
            .group_by(WakatimeDuration.user_id)
            .having(db_funcs.count() < timeframe_day_span)
    )

    # Fetch those user ids ...
    user_ids = await session.scalars(stmt)

    # Return them.
    return list(user_ids.all())


async def wakatime_token_lookup_generator(
    session : AsyncSession,
    user_ids : list[UUID],
    *,
    skip_missing_credentials : bool = False,
    expired_oauth_behaviour : Literal["skip", "error", "refresh"] = "error"
) -> AsyncGenerator[WakatimeTokens, None]:
    """
    A generator which yields wakatime tokens retrieved from the database
    for the provided user UUIDs.
    """
    # This is probably such a stupidly excessive way to do this.

    for uuid in user_ids:
        creds = await session.get(OAuth2Credentials, (uuid, "wakatime"))

        # If we don't get any credentials back from the database
        if creds is None:

            # Throw an error if we aren't just skipping these problems.
            if not skip_missing_credentials:
                raise ValueError(
                    f"User id {uuid} does not have wakatime credentials in the database."
                )
            
            # If we *are* just skipping these problems, then we can just go to
            # the next iteration
            continue

        # Next, check that the tokens are actually valid (by expiry time)
        if is_oauth_expired(creds):

            # If they are expired, then we either throw an error, skip this user, or 
            # trigger a refresh for the user's tokens.
            if expired_oauth_behaviour == "error":
                raise ValueError(
                    f"User id {uuid} has expired credentials, and we're not refreshing them!"
                )
            
            # TODO: Refresh them
            elif expired_oauth_behaviour == "refresh":
                raise NotImplementedError()
            
            # Skip behaviour
            else:
                continue

        # At the point, the access token MUST be valid, so we can decrypt them
        # and yield them through the generator
        decrypted_access_token = tokens_utils.decrypt(creds.access_token)
        decrypted_refresh_token = tokens_utils.decrypt(creds.refresh_token)

        # FIXME: In most places, we do not need the refresh token, so refactoring
        # some of the codebase to only require it where necessary may be an ideal
        # task for future polish.
        # We're returning this whole object here because *most* functions in this
        # codebase use the object.
        yield WakatimeTokens(
            user_id = uuid,
            access_token = decrypted_access_token,
            refresh_token = decrypted_refresh_token
        )

__all__ = ["is_oauth_expired", "update_oauth_tokens", "recache_wakatime_profile"]
