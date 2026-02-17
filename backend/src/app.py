from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

from .db import run_migrations, start_database_engine, shutdown_database_engine
from .jobs.scheduler import init_job_scheduler, kill_job_scheduler, JobScheduler
from .utils.env import get_required_env

from .routers import ping_router, user_router

def add_presceduled_jobs(js: JobScheduler) -> None:
    """
    Handles setting up jobs which are pre-scheduled or reoccuring.
    """
    js.add_job(
        lambda: print("This runs every 5s!"), "interval", seconds=5, id="ping_job"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and graceful shutdown
    of resources depended on by the api.
    """
    # Load any environment variable files that may be present
    load_dotenv()

    # GRACEFUL STARTUP      -------------------------

    # Start the database engine
    DB_URL = get_required_env("DATABASE_URL")
    start_database_engine(db_url=DB_URL)

    # Run any pending migrations
    await run_migrations()

    # Start the job scheduler and add any prescheduled jobs to it
    job_scheduler = init_job_scheduler()
    add_presceduled_jobs(js=job_scheduler)

    # yield -> the api is ready to start!
    yield

    # GRACEFUL SHUTDOWN     -------------------------
    kill_job_scheduler(wait=False)

    await shutdown_database_engine()


app = FastAPI(lifespan=lifespan)

app.include_router(ping_router)
app.include_router(user_router)
