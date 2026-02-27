from ..db import get_session
from ..db.models import WeeklyLeaderboard, WakatimeDuration
from ..db.helpers import wakatime_token_lookup_generator, get_user_ids_with_incomplete_durations, evil_duration_fetching_function
from ..wakatime import WakatimeStartEndTimeframe

from sqlalchemy import delete, insert, literal, select, func as db_funcs
from logging import getLogger
from datetime import date, timedelta
import asyncio

MAX_CONCURRENT_LEADERBOARD_JOBS = 4
LOGGER = getLogger(__name__)

async def leaderboard_job() -> None:
    """
    Should run every hour or so to refresh the leaderboard
    """

    LOGGER.info("Recalculating weekly leaderboards...")

    # First we need to figure out when "this" week actually is. We're building a timeframe
    # here because most of the functions down the line use it
    today = date.today()
    start_of_week = date.fromisocalendar(today.year, today.isocalendar().week, 1)

    timeframe = WakatimeStartEndTimeframe(
        start = start_of_week.strftime(r"%Y-%m-%d"),
        end = today.strftime(r"%Y-%m-%d")
    )

    async with get_session() as session:

        # This will gather all the users that we need to recache
        # NOTE: incomplete_today_check will check any record for today against
        # the refresh threshold to see if it is out of date.
        users_to_recache = await get_user_ids_with_incomplete_durations(
            session = session,
            timeframe = timeframe,
            incomplete_today_check = True,
            today_refresh_threshold = timedelta(hours=1)
        )

        # We need to keep track of two things for the next part:
        # 1. How many concurrent requests are actually happening, we use a semaphore
        #    to do this, which will help keep us from flooding Wakatime or our database
        # 2. We need to keep track of all of our tasks and whether or not they are
        #    actually completed or not, as only then can we move onto calculating the
        #    leaderboard.
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_LEADERBOARD_JOBS)
        fetch_tasks = []

        # This wakatime_token_lookup_generator is an async generator that will provide us with
        # user tokens straight from the database -- or in the event that a token is expired,
        # will provide us with fresh tokens.
        # TODO: The refreshing bit doesn't work, but it doesn't really matter, as the waka tokens dont expire for a year
        async for tokens in wakatime_token_lookup_generator(
            session = session,
            user_ids = users_to_recache,
            expired_oauth_behaviour = "skip",
            skip_missing_credentials = True
        ):
            
            # We wrap the evil_duration_fetching_function with a context manager for the
            # semaphore, which will release() when the inner coroutine is completed
            async def evil_wrapped_with_semaphore():
                async with semaphore:
                    await evil_duration_fetching_function(
                        session = session,
                        tokens = tokens,
                        timeframe = timeframe
                    )

            # We create a task and tell asyncio to start it right away. It returns a handle that
            # we keep track of in an array. This way we're not waiting on any specific job, but ALL
            # incomplete jobs
            fetching_task = asyncio.create_task(evil_wrapped_with_semaphore())
                    
            fetch_tasks.append(fetching_task)

        # Waiting for all of the incomplete coroutines to finish
        await asyncio.gather(*fetch_tasks)

        # Commit any new durations to the database. If we got to this point, none of the above
        # code should have errored and we don't want to lose that data
        await session.flush()

        # Delete all the pre-existing records for this week
        await session.execute(
            delete(WeeklyLeaderboard).where(
                WeeklyLeaderboard.week_start == start_of_week
            )
        )

        # This is just a func we use twice in the aggregation to add all of the
        # WakatimeDurations' totals together
        total_seconds_sum = db_funcs.sum(WakatimeDuration.total_seconds)

        # The select() statement in here is what is getting inserted into the
        # WeeklyLeaderboards table.
        crazy_aggregation_stmt = (
            select(
                literal(start_of_week).label("week_start"),
                WakatimeDuration.user_id.label("user_id"),
                total_seconds_sum.label("total"),
                db_funcs.rank().over(order_by=total_seconds_sum).label("rank")
            )
            .where(WakatimeDuration.date.between(start_of_week, today))
            .group_by(WakatimeDuration.user_id)
        )

        stmt = insert(WeeklyLeaderboard).from_select(
            [
                WeeklyLeaderboard.week_start,
                WeeklyLeaderboard.user_id,
                WeeklyLeaderboard.total,
                WeeklyLeaderboard.rank
            ],
            crazy_aggregation_stmt
        )

        await session.execute(stmt)

        # After we're done the above statement, we can commit the
        # changes and close the database
        await session.commit()

        LOGGER.info("Weekly leaderboard successfully recalculated!")