from typing import Annotated

from fastapi.routing import APIRouter
from fastapi import HTTPException, Path
from datetime import date

from ..db import get_session as get_db_session
from ..db.helpers import evil_duration_fetching_function
from ..dependencies.auth import TokenDependencyType
from ..wakatime import WakatimeISOWeekTimeframe, WakatimeSingleDayTimeframe
from ..models.durations import (
    DurationResponseModel,
    BulkDurationResponseModel,
    LanguageBreakdownModel,
)

router = APIRouter(tags=["durations"])


@router.get("/durations/week")
async def get_durations_for_current_week(tokens: TokenDependencyType):
    """
    Returns the user's durations for the current week
    """
    iso_date = date.today().isocalendar()

    # We just hand off this request to the other request handler using the
    # current date, nothing complicated :/
    return await get_durations_for_week(
        iso_week=iso_date.week, year=iso_date.year, tokens=tokens
    )


@router.get("/durations/week/{year}/{iso_week}")
async def get_durations_for_week(
    tokens: TokenDependencyType, year: int, iso_week: int = Path(ge=1, le=52)
) -> BulkDurationResponseModel:
    """
    Returns the user's durations for the provided week.
    """

    async with get_db_session() as session:
        try:
            # Ah yes, the evil duration fetching function...
            user_durations = await evil_duration_fetching_function(
                session=session,
                tokens=tokens,
                timeframe=WakatimeISOWeekTimeframe(iso_week=iso_week, year=year),
            )
        except ValueError:
            raise HTTPException(
                status_code=500, detail="Failed to fetch new durations from wakatime."
            )

        # Construct a new list to hold all the durations responses
        # (one for each day of the week)
        duration_responses = [
            DurationResponseModel(
                date=duration.date,
                languages=[
                    LanguageBreakdownModel(
                        name=lang.language, total_seconds=lang.total_seconds
                    )
                    for lang in duration.languages
                ],
                last_cached_at=duration.last_cached_at,
                total_seconds=duration.total_seconds,
            )
            for duration in user_durations
        ]

        # hahaha dont forget to commit the changes like I did when I first
        # wrote this function smh...
        await session.commit()

        return BulkDurationResponseModel(durations=duration_responses)

@router.get("/durations/day")
async def get_duration_for_today(
    tokens : TokenDependencyType
) -> DurationResponseModel:
    """
    Returns the user's durations for today.
    """
    today = date.today()

    return await get_durations_for_day(
        tokens = tokens,
        year = today.year,
        month = today.month,
        day = today.day
    )

@router.get("/durations/day/{year}/{month}/{day}")
async def get_durations_for_day(
    tokens : TokenDependencyType,
    year : int,
    month : Annotated[int, Path(ge=1, le=12)],
    day : Annotated[int, Path(ge=1, le=31)]
) -> DurationResponseModel:
    """
    Returns a single duration response for the provided day
    """

    # Construct a date object from args
    date_object = date(
        year = year,
        month = month,
        day = day
    )

    async with get_db_session() as session:

        try:
            durations_list = await evil_duration_fetching_function(
                session = session,
                tokens = tokens,
                timeframe = WakatimeSingleDayTimeframe(day=date_object)
            )
        
        except ValueError:
            # A ValueError usually gets raised by the above call if the response 
            # from wakatime is non-OK on a recache.
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch new durations from wakatime."
            )
        
        if len(durations_list) != 1:
            raise HTTPException(
                status_code=500,
                detail="Retrieved non-singular or null result from evil duration fetching function"
            )
        
        # Since we know the length has to be one, then we know
        # we can get the single duration
        duration = durations_list[0]

        # We construct the model here because we need to do it BEFORE
        # committing so we dont lose access to the `WakatimeDuration` 
        # sqlalchemy model.
        resp_model = DurationResponseModel(
            date = duration.date,
            languages = [
                LanguageBreakdownModel(
                    name = lang.language, 
                    total_seconds = lang.total_seconds
                )
                for lang in duration.languages
            ],
            total_seconds = duration.total_seconds,
            last_cached_at = duration.last_cached_at
        )

        # The nefarious aforementioned commit.
        await session.commit()

    return resp_model


__all__ = ["router"]
