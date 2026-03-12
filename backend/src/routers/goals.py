from typing import Annotated

from fastapi import Body, HTTPException, Path
from fastapi.routing import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete, select, func as db_func, bindparam, case, Float, update
from sqlalchemy.dialects.postgresql import insert
from datetime import date

from src.db.models import Goals, WakatimeDuration, GoalEnum
from src.db import get_session
from src.dependencies.auth import UserIDDependencyType
from src.models.goals import GoalResponseModel, GoalCreationRequest, GoalUpdateRequest

router = APIRouter(tags=["goals"])

# A limit on the maximum number of goals a user can have set
MAX_COUNT_OF_USER_GOALS = 8


@router.get("/goals")
async def get_goals(
    user_id: UserIDDependencyType,
) -> list[GoalResponseModel]:

    # TODO: If a user has not queried their durations recently the database may not be able
    #       to accurately determine if they've "reached" a goal or not. -- i.e., progress
    #       will not be properly shown.

    date_binding = bindparam("date")
    user_binding = bindparam("user_id")

    # We define a common table expression here to handle retrieving the aggregate durations
    # for the user, that way we can calculate how close a user has come to completing their goal
    # (or how many times over they have completed it)
    duration_totals_cte = (
        select(
            WakatimeDuration.user_id,
            # we coalesce here in case sum() returns a null value from having no rows to add.
            # this column gets labelled as "daily_goal_seconds", we'll refer to it later.
            db_func.coalesce(
                # take the sum of all the seconds
                db_func.sum(WakatimeDuration.total_seconds)
                # then we filter here by date (only rows matching this filter will be summed)
                .filter(WakatimeDuration.date == date_binding),
                # coalesce default
                0,
            ).label("daily_goal_seconds"),
            # very similar to above, but for weekly-scoped goals, labelled as "weekly_goal_seconds"
            db_func.coalesce(
                db_func.sum(WakatimeDuration.total_seconds)
                # This filter here checks to see if the date of the duration we're pulling is
                # older than the start of the week for the provided date (truncate pushes date_binding to monday)
                .filter(
                    WakatimeDuration.date >= db_func.date_trunc("week", date_binding)
                ),
                0,
            ).label("weekly_goal_seconds"),
        )
        .where(WakatimeDuration.user_id == user_binding)
        .group_by(WakatimeDuration.user_id)
        .cte("duration_totals")
    )

    # This statement specifically decides which of either the weekly or daily columns should be selected.
    # This feels like more of an *expression* than a statement, but it basically lets us conditionally calculate
    # the progress based on goal scopes.
    progress_stmt = case(
        (
            Goals.timeframe == GoalEnum.DAILY,
            duration_totals_cte.c.daily_goal_seconds.cast(Float)
            / (Goals.minutes * 60)
            * 100,
        ),
        (
            Goals.timeframe == GoalEnum.WEEKLY,
            duration_totals_cte.c.weekly_goal_seconds.cast(Float)
            / (Goals.minutes * 60)
            * 100,
        ),
    ).label("goal_progress_percentage")

    # The actual statement we're using to query all this data.
    # We join the CTE we made earlier, and then use the progress statement we defined to
    # pull only the data we need from it (conditionally based off of goal scope).
    stmt = (
        select(Goals, progress_stmt)
        .join(duration_totals_cte, duration_totals_cte.c.user_id == Goals.user_id)
        .where(Goals.user_id == user_binding)
    )

    async with get_session() as session:
        # Here we pass through the bindings we made and execute the statement
        resp = await session.execute(stmt, {"date": date.today(), "user_id": user_id})

        # Return data array
        ret_data = []

        # Unpacking all that sweet sweet goal data
        for goal, progress in resp.all():
            ret_data.append(
                GoalResponseModel(
                    goal_id=goal.id,
                    timeframe=goal.timeframe,
                    minutes=goal.minutes,
                    progress=progress,
                )
            )

    # Finally, return allat
    return ret_data


@router.post("/goals")
async def create_new_goal(
    user_id: UserIDDependencyType,
    payload: GoalCreationRequest = Body(
        examples=[GoalCreationRequest(timeframe=GoalEnum.WEEKLY, minutes=180)]
    ),
) -> PlainTextResponse:
    """
    Creates a new goal for the user, the user can have multiple goals if they so choose (up to a fixed limit).

    The `minutes` field must be greater than zero, and the valid values for timeframe are `daily` and `weekly`
    """

    stmt = insert(Goals).values(
        {"user_id": user_id, "timeframe": payload.timeframe, "minutes": payload.minutes}
    )

    async with get_session() as session:
        # Before we create a new goal, we restrict the user to having only a certain number of goals set.
        goal_count = await session.scalar(
            select(db_func.count()).select_from(Goals).where(Goals.user_id == user_id)
        )

        # NOTE: COUNT() doesn't return NULL here ever, so this is just a condition to appease
        #       the type-hinting gods.
        if goal_count is not None and goal_count >= MAX_COUNT_OF_USER_GOALS:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum number of goals is {MAX_COUNT_OF_USER_GOALS}",
            )

        # If the user has less than the maximum number of goals, let them have their new goal
        await session.execute(stmt)
        await session.commit()

    return PlainTextResponse(status_code=200)


@router.patch("/goals/{goal_id}")
async def update_goal(
    user_id: UserIDDependencyType,
    goal_id: Annotated[int, Path()],
    payload: GoalUpdateRequest = Body(default=GoalUpdateRequest()),
) -> PlainTextResponse:
    """
    Updates a goal that the user owns based on the provided id.

    If the user tries to update a goal which doesn't belong to them, it returns a 404.

    All fields in the update payload are nullable, if null, the field will not be updated and the
    original value will be maintained. If any field is omitted, its value will default to null.
    """

    update_values = {}

    if payload.timeframe:
        update_values["timeframe"] = payload.timeframe

    if payload.minutes:
        update_values["minutes"] = payload.minutes

    if not update_values:
        raise HTTPException(
            status_code=400, detail="Goal update payload cannot be empty."
        )

    update_query = (
        update(Goals)
        .where(Goals.user_id == user_id)
        .where(Goals.id == goal_id)
        .values(**update_values)
        .returning(Goals.id)
    )

    async with get_session() as session:
        update_result = await session.scalar(update_query)

        # If we failed to match any rows, then either:
        #   - the user doesn't own the goal
        #   - the goal doesn't exist at all
        # we should return a 404.
        if update_result is None:
            raise HTTPException(status_code=404)

        await session.commit()

        return PlainTextResponse(status_code=200, content="Goal updated successfully")


@router.delete("/goals/{goal_id}")
async def delete_goal(
    user_id: UserIDDependencyType, goal_id: Annotated[int, Path()]
) -> PlainTextResponse:
    """
    Deletes the goal using the provided id.

    If the user tries to delete a goal which they do not own, or a goal which does not exist
    this endpoint will return a 404.
    """

    stmt = (
        delete(Goals)
        .where(Goals.user_id == user_id)
        .where(Goals.id == goal_id)
        .returning(Goals.id)
    )

    async with get_session() as session:
        delete_result = await session.scalar(stmt)

        if delete_result is None:
            raise HTTPException(status_code=404)

        await session.commit()

    return PlainTextResponse(status_code=200, content="Goal deleted successfully")
