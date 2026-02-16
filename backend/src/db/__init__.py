from contextlib import asynccontextmanager
from typing import AsyncIterator
import alembic.config
import alembic.command
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncConnection,
    AsyncEngine,
)

#
#       DATABASE ENGINE SINGLETON WRAPPER THINGY
#


class DatabaseSingleton(object):
    """
    A very hacky singleton object that modifies its class definition
    in order to keep track of a single instance of itself.
    """

    engine: AsyncEngine | None
    sessionmaker: async_sessionmaker[AsyncSession] | None

    def __init__(self, db_url: str) -> None:
        # Create the engine:
        #   The engine is responsible for the connection to the database.
        self.engine = create_async_engine(url=db_url)

        # Create the session maker:
        #   The session maker is responsible for creating individual sessions
        #   for transactions.
        self.sessionmaker = async_sessionmaker(bind=self.engine)

    async def die(self) -> None:
        """
        Closes the connections and whatnot for the singleton.

        This makes the singleton unusable, so only do this when you
        are truly finished with it and ready to whisk it away into
        the trash like yesterday's rubbish!
        """

        # Make sure we didn't already kill the database singleton
        if self.engine is None:
            raise ValueError("Database singleton cannot die: singleton is already dead")

        # If it's still alive, get rid of the connection
        await self.engine.dispose(close=True)

        # Set the engine to null because it's no longer connected.
        self.engine = None

        # Set the sessionmaker to none because it relies on the engine.
        self.sessionmaker = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        """
        Returns a context manager for an async connection
        to the database.

        You probably dont want to use this one though, use the
        .session context manager.
        """
        # le sanity check
        if self.engine is None:
            raise ValueError(
                "Failed to get connection context manager: engine is not initialized"
            )

        # Creates a new connection and then yields it. If there is some sort of error
        # that happens, our wrapper reverts any changes made during this connection.
        async with self.engine.begin() as connection:
            try:
                yield connection
            except Exception as _:
                await connection.rollback()
                raise

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Returns a context manager for an async db session.
        """
        # le sanity check numero two
        if self.sessionmaker is None:
            raise ValueError(
                "Failed to get session context manager: session maker is not initialized"
            )

        # Creates a new session and then yields it. Very similar to the connect context manager.
        # This closes the session when it is finished.
        async with self.sessionmaker.begin() as session:
            try:
                yield session
            except Exception as _:
                await session.rollback()
                raise
            finally:
                await session.close()


def get_database_singleton() -> DatabaseSingleton:
    singleton = getattr(DatabaseSingleton, "instance", None)

    if not singleton:
        raise ValueError("Failed to get database singleton: instance not initialized")

    return singleton


#
#       LIFESPAN FUNCTIONS
#


def start_database_engine(*, db_url: str) -> None:
    """
    Makes the database functional by creating the singleton wrapper.
    """

    if hasattr(DatabaseSingleton, "instance"):
        raise ValueError(
            "Cannot init database singleton: it's already initialized, what???"
        )

    new_singleton = DatabaseSingleton(db_url=db_url)

    setattr(DatabaseSingleton, "instance", new_singleton)


async def shutdown_database_engine() -> None:
    """
    Shuts down the database engine gracefully.

    This should only be called at the end of the lifespan
    function doohickey for the FastAPI app.
    """
    await get_database_singleton().die()


#
#       SHORTHAND FUNCTIONS
#


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Shorthand for get_database_singleton().session() context manager
    """
    async with get_database_singleton().session() as session:
        yield session


@asynccontextmanager
async def get_connection() -> AsyncIterator[AsyncConnection]:
    """
    Shorthand for get_database_singleton().connect() context manager
    """
    async with get_database_singleton().connect() as connection:
        yield connection


#
#       DATABASE MIGRATIONS
#        (MAINTAINS SCHEMA)
#


async def run_migrations() -> None:
    """
    Nightmarishly complicated migrations function.

    Running this will attempt to migrate the database to the most
    up-to-date revision.
    """

    # Creates an instance of an alembic config
    cfg = alembic.config.Config("alembic.ini")

    # Define a wrapper which consumes an established connection
    # and passes it through a modified "connectable" attribute in the config
    # so we can work around a weird async-loop-has-already-been-defined error
    def migration_runner(con, cfg):
        cfg.attributes["connectable"] = con

        # "head" denotes the revision at the head of the tree
        alembic.command.upgrade(cfg, "head")

    # run the command wrapper with an established connection
    async with get_connection() as connection:
        await connection.run_sync(migration_runner, cfg)


__all__ = [
    "DatabaseSingleton",
    "start_database_engine",
    "shutdown_database_engine",
    "get_database_singleton",
    "get_connection",
    "get_session",
    "run_migrations",
]
