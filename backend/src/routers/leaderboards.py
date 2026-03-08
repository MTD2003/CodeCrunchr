from fastapi import HTTPException
from fastapi.routing import APIRouter
from uuid import UUID
from datetime import date
from sqlalchemy import select

from ..dependencies.auth import UserIDDependencyType
from ..db.models import WeeklyLeaderboard, WakatimeUserProfile
from ..db import get_session
from ..models.leaderboards import LeaderboardRanking, LeaderboardResponse, WakatimeProfile

router = APIRouter(
    tags=["leaderboards"]
)

@router.get("/leaderboard")
async def get_leaderboard(
    _ : UserIDDependencyType,
) -> LeaderboardResponse:
    
    today = date.today()

    current_week_start = date.fromisocalendar(
        year = today.year,
        week = today.isocalendar().week,
        day = 1
    )

    async with get_session() as session:

        stmt = (
            select(WeeklyLeaderboard, WakatimeUserProfile)
                .where(WeeklyLeaderboard.week_start == current_week_start)
                .order_by(WeeklyLeaderboard.rank)
                .limit(100)
                .join(WakatimeUserProfile, WakatimeUserProfile.user_id == WeeklyLeaderboard.user_id, isouter=True)
        )

        res = await session.execute(stmt)

        return LeaderboardResponse(
            leaderboard = [
                LeaderboardRanking(
                    user_id = leaderboard_placement.user_id,
                    rank = leaderboard_placement.rank,
                    total_seconds = leaderboard_placement.total,
                    profile = None if profile is None else WakatimeProfile(
                        user_id = str(profile.user_id),
                        display_name = profile.display_name,
                        full_name = profile.full_name,
                        username = profile.username,
                        is_photo_public = profile.is_photo_public,
                        photo_url = profile.photo_url,
                        last_cached_at = profile.last_cached_at,
                    )
                ) for leaderboard_placement, profile in res]
        )


@router.get("/leaderboard/placement")
async def get_leaderboard_placement_for_current_user(
    user_id : UserIDDependencyType    
) -> LeaderboardRanking:
    """
    Shorthand function that returns the current user's placement on the 
    weekly leaderboard
    """
    return await get_leaderboard_placement_for_user(
        _ = user_id,
        user_id = user_id
    )

@router.get("/leaderboard/placement/{user_id}")
async def get_leaderboard_placement_for_user(
    _ : UserIDDependencyType,
    user_id : UUID
) -> LeaderboardRanking:
    
    # We only care of the user's placement today
    today = date.today()

    current_week_start = date.fromisocalendar(
        year = today.year,
        week = today.isocalendar().week,
        day = 1
    )

    async with get_session() as session:

        # Select the user's current leaderboard placement for this week,
        # as well as their profile
        stmt = (
            select(WeeklyLeaderboard, WakatimeUserProfile)
                .where(WeeklyLeaderboard.week_start == current_week_start)
                .where(WeeklyLeaderboard.user_id == user_id)
                .join(WakatimeUserProfile, WakatimeUserProfile.user_id == user_id, isouter=True)
        )

        # NOTE: Can use scalars() here because the join() gets voided
        res = (await session.execute(stmt)).one_or_none()

        if res is None:
            raise HTTPException(
                status_code = 404,
                detail = "User has not been calculated in the leaderboard yet. Check back later"
            )
        
        # Unpack the response (it is basically a tuple)
        leaderboard_placement, profile = res
        profile : WakatimeUserProfile

        # Build the leaderboard ranking response and return it
        return LeaderboardRanking(
            user_id = leaderboard_placement.user_id,
            rank = leaderboard_placement.rank,
            total_seconds = leaderboard_placement.total,
            profile = None if profile is None else WakatimeProfile(
                user_id = str(profile.user_id),
                display_name = profile.display_name,
                full_name = profile.full_name,
                username = profile.username,
                is_photo_public = profile.is_photo_public,
                photo_url = profile.photo_url,
                last_cached_at = profile.last_cached_at,
            )
        )
        
__all__ = ["router"]