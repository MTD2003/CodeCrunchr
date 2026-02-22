from contextlib import asynccontextmanager
import sys
from fastapi import FastAPI
from dotenv import load_dotenv
import logging

load_dotenv()

from .db import run_migrations, start_database_engine, shutdown_database_engine  # noqa: E402
from .jobs.scheduler import init_job_scheduler, kill_job_scheduler, JobScheduler  # noqa: E402
from .utils.env import get_required_env  # noqa: E402

from .routers import ping_router, user_router  # noqa: E402

LOGGER = logging.getLogger(__name__)
SETUP_LOGGING = lambda: logging.basicConfig(  # noqa: E731
    level=logging.DEBUG,
    stream=sys.stdout,
    format="[%(asctime)s] %(levelname)-5.5s [%(name)s.%(funcName)s] %(message)s",
    force=True,
    datefmt=r"%F %H:%M:%S",
)
SETUP_LOGGING()


def add_presceduled_jobs(js: JobScheduler) -> None:
    """
    Handles setting up jobs which are pre-scheduled or reoccuring.
    """
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and graceful shutdown
    of resources depended on by the api.
    """
    # Load any environment variable files that may be present

    # GRACEFUL STARTUP      -------------------------

    # Start the database engine
    DB_URL = get_required_env("DATABASE_URL")
    start_database_engine(db_url=DB_URL)

    # Run any pending migrations
    await run_migrations()

    # Start the job scheduler and add any prescheduled jobs to it
    job_scheduler = init_job_scheduler()
    add_presceduled_jobs(js=job_scheduler)

    LOGGER.info("The app is ready to start!")

    # yield -> the api is ready to start!
    yield

    LOGGER.info("Attempting to shutdown the app gracefully...")

    # GRACEFUL SHUTDOWN     -------------------------
    kill_job_scheduler(wait=False)

    await shutdown_database_engine()

    LOGGER.info("Bye!")


app = FastAPI(lifespan=lifespan)

app.include_router(ping_router)
app.include_router(user_router)
