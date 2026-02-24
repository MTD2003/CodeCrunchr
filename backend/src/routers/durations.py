from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from fastapi import HTTPException, Path
from datetime import date, timedelta
from sqlalchemy import func as db_func, extract, select

from ..db.models import WakatimeDuration, WakatimeLanguageDuration
from ..db import get_session as get_db_session
from ..db.helpers import get_cached_user_durations, update_user_durations
from ..dependencies.auth import TokenDependencyType
from ..wakatime.summaries import get_summaries
from ..wakatime import WakatimeISOWeekTimeframe, WakatimeStartEndTimeframe
from ..models.durations import DurationResponseModel, BulkDurationResponseModel, LanguageBreakdownModel

router = APIRouter(tags=["durations"])

@router.get("/durations/week")
async def get_durations_for_current_week(
    tokens: TokenDependencyType
):
    """
    Returns the user's durations for the current week
    """
    iso_date = date.today().isocalendar()

    # We just hand off this request to the other request handler using the
    # current date, nothing complicated :/
    return await get_durations_for_week(
        iso_week = iso_date.week,
        year = iso_date.year,
        tokens = tokens
    )

@router.get("/durations/week/{year}/{iso_week}")
async def get_durations_for_week(
    tokens : TokenDependencyType,
    year : int,
    iso_week : int = Path(ge=1, le=52)
) -> BulkDurationResponseModel:
    """
    Returns the user's durations for the provided week.
    """

    async with get_db_session() as session:

        user_durations, needs_recache = await get_cached_user_durations(
            session = session,
            duration_timeframe = WakatimeISOWeekTimeframe(iso_week=iso_week, year=year),
            user_id = tokens["user_id"],
            eager_load = True
        )

        # If the durations do need a recache
        if needs_recache is not None:

            # Unpack the start, end pair from the needs_recache object
            start, end = needs_recache

            # Construct a proper timeframe object to use in a wakatime request
            recache_tf = WakatimeStartEndTimeframe(
                start=start.strftime(r"%Y-%m-%d"),
                end=end.strftime(r"%Y-%m-%d")
            )

            # This is the aforementioned wakatime request :)
            new_summary = await get_summaries(
                tokens = tokens,
                user = "current",
                timeframe = recache_tf
            )

            # If fetching the summaries fails for some reason, then return
            # a 500 to the user.
            if new_summary.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get summaries from wakatime"
                )

            # Otherwise, If we got summaries back we can unwrap them and push them
            # to the database.
            new_durations = await update_user_durations(
                session, tokens, new_summary.unwrap()
            )

            today = date.today()

            # Now we need to build a complete replacement for `user_durations`
            # incorporating the data from `new_durations` (ugh)
            tmp_user_durations = []

            # Calculate the maximum number of days possible,
            # The max is 7 if the iso_week provided is not currently ongoing,
            # Otherwise, the max number of days is the zero-indexed weekday plus 1 (inclusive of today)
            # Logically, that might make no sense, but it *is* correct. womp womp
            max_days_in_week = 7 if today.isocalendar().week != iso_week else today.weekday() + 1

            # This while-loop builds a new `user_durations` by doing some weird
            # indexing nonsense and figuring out which date comes "next" while prioritizing
            # the new durations over the old 
            # Assume: 
            # * Xn == Yn == None is impossible
            # * Yn is always prioritized (most recent data)
            xn, yn = 0, 0
            while len(tmp_user_durations) < max_days_in_week:

                # These should both be sorted.
                duration_y = new_durations[yn]
                duration_x = None if xn >= len(user_durations) else user_durations[xn]

                if duration_x is not None and duration_x.date < duration_y.date:
                    xn += 1
                    tmp_user_durations.append(duration_x)
                else:
                    yn += 1
                    tmp_user_durations.append(duration_y)

            # Now we take the newly built user_durations and assign it to the old variable for later use
            # in the endpoint
            user_durations = tmp_user_durations

        # Construct a new list to hold all the durations responses 
        # (one for each day of the week)
        duration_responses = [
            DurationResponseModel(
                date = duration.date,
                languages = [
                    LanguageBreakdownModel(
                        name = lang.language,
                        total_seconds = lang.total_seconds
                    )
                    for lang in duration.languages
                ],
                last_cached_at = duration.last_cached_at,
                total_seconds = duration.total_seconds,
            )
            for duration in user_durations
        ]

        # hahaha dont forget to commit the changes like I did when I first
        # wrote this function smh...
        await session.commit()

        return BulkDurationResponseModel(
            durations = duration_responses
        )

__all__ = ["router"]

