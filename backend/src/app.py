from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

from .db import run_migrations, start_database_engine, shutdown_database_engine
from .utils.env import get_required_env

from .routers import ping_router


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

    # yield -> the api is ready to start!
    yield

    # GRACEFUL SHUTDOWN     -------------------------
    await shutdown_database_engine()


app = FastAPI(lifespan=lifespan)

app.include_router(ping_router)
