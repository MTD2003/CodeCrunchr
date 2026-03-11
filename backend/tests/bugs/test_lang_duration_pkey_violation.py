import pytest
import pytest_asyncio
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

from src.db.helpers import update_user_durations
from src.db.models import User
from src.wakatime import WakatimeTokens
from src.wakatime.summaries import (
    SummaryResponseModel,
    DailyAverageModel,
    CumulativeTotalModel,
    SummarySections,
    Range,
    GrandTotalModel,
)

test_data: list[SummaryResponseModel] = [
    # Range response is correct, but no data is actually returned
    SummaryResponseModel(
        data=[],
        cumulative_total=CumulativeTotalModel(
            seconds=0, text="", decimal="", digital=""
        ),
        daily_average=DailyAverageModel(
            days_including_holidays=0,
            days_minus_holidays=0,
            holidays=0,
            seconds=0,
            seconds_including_other_language=0,
            text="",
            text_including_other_language="",
        ),
        start="2026-01-01T03:59:59Z",
        end="2026-01-01T04:00:00Z",
    ),
    # Some data is returned, but range is different
    SummaryResponseModel(
        data=[
            SummarySections(
                grand_total=GrandTotalModel(
                    hours=0,
                    minutes=0,
                    total_seconds=0.0,
                    digital="",
                    decimal="",
                    text="",
                    human_additions=0,
                    human_deletions=0,
                    ai_additions=0,
                    ai_deletions=0,
                ),
                categories=[],
                dependencies=[],
                editors=[],
                languages=[],
                machines=[],
                operating_systems=[],
                projects=[],
                # We don't use this data anywhere important
                range=Range(date="", start="", end="", text="", timezone=""),
            )
        ],
        cumulative_total=CumulativeTotalModel(
            seconds=0, text="", decimal="", digital=""
        ),
        daily_average=DailyAverageModel(
            days_including_holidays=0,
            days_minus_holidays=0,
            holidays=0,
            seconds=0,
            seconds_including_other_language=0,
            text="",
            text_including_other_language="",
        ),
        start="2026-01-01T03:59:59Z",
        end="2026-01-03T04:00:00Z",
    ),
]


# This will create "mock tokens", which doesnt actually make tokens
# but does make a `User` record and then cleans it up after each function
# run.
@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def mock_tokens(test_db: AsyncSession) -> AsyncGenerator[WakatimeTokens, None]:

    user_id = UUID(int=0)
    new_user = User(id=user_id)

    test_db.add(new_user)

    await test_db.flush()

    yield WakatimeTokens(user_id=user_id, access_token="", refresh_token="")

    await test_db.delete(new_user)

    await test_db.flush()


@pytest.mark.parametrize("summary", test_data)
@pytest.mark.asyncio(loop_scope="session")
async def test_lang_duration_pkey_violation(
    test_db: AsyncSession, mock_tokens: WakatimeTokens, summary: SummaryResponseModel
):

    # We were getting an error where there was a NOT NULL violation
    # happening (due to primary keys). It occurred because the wakatime durations
    # were sometimes incomplete or null. I created two test cases to sniff out the
    # error :/

    await update_user_durations(session=test_db, tokens=mock_tokens, summary=summary)

    # If this function passes, then the test passes. SQLAlchemy will throw a hissy fit
    # if it runs into the issue again.
