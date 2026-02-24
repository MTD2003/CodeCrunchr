from fastapi.routing import APIRouter
from fastapi import HTTPException, Path
from datetime import date

from ..db import get_session as get_db_session
from ..db.helpers import evil_duration_fetching_function
from ..dependencies.auth import TokenDependencyType
from ..wakatime import WakatimeISOWeekTimeframe
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


__all__ = ["router"]
