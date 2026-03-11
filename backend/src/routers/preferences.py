from fastapi import Body
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRouter
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

from src.dependencies.auth import UserIDDependencyType
from src.db.models import UserPreferences
from src.db import get_session

router = APIRouter(tags=["preferences"])


@router.get("/preferences")
async def get_user_preferences(user_id: UserIDDependencyType) -> JSONResponse:
    """
    Returns the entire preference payload that was previously pushed to the database.

    If no preferences have been set, this endpoint returns an empty JSON object.
    """

    stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)

    async with get_session() as session:
        resp = await session.scalar(stmt)

        if resp is None:
            return JSONResponse(content={})

        return JSONResponse(resp.preferences)


@router.post("/preferences")
async def update_user_preferences(
    user_id: UserIDDependencyType,
    payload: dict = Body(
        default={}, examples=[{"some_preference": True, "other_preference": 69}]
    ),
) -> Response:
    """
    Updates the authenticated user's preferences with the provided JSON payload. This will
    overwrite any previously set payloads.

    Payloads must be json serializable objects.
    """

    stmt = insert(UserPreferences).values(
        {
            "user_id": user_id,
            "last_updated": datetime.now(tz=None),
            "preferences": payload,
        }
    )

    stmt_with_conflict_clause = stmt.on_conflict_do_update(
        index_elements=["user_id"],
        set_={
            "last_updated": stmt.excluded.last_updated,
            "preferences": stmt.excluded.preferences,
        },
    )

    async with get_session() as session:
        await session.execute(stmt_with_conflict_clause)
        await session.commit()

    # De bluetooth device has connected successfullay
    return Response(status_code=200, content="User preferences updated successfully!")


@router.delete("/preferences")
async def reset_user_preferences(user_id: UserIDDependencyType) -> Response:
    """
    Resets a user's preferences payload (by deleting it entirely).
    """

    stmt = delete(UserPreferences).where(UserPreferences.user_id == user_id)

    async with get_session() as session:
        await session.execute(stmt)
        await session.commit()

    return Response(status_code=200, content="Your user preferences have been cleared!")
