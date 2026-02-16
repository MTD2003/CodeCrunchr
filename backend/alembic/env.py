from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool

from alembic import context

import asyncio
from os import getenv

load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(
        config.config_file_name,
        # WHYYYY??????
        disable_existing_loggers=False,
    )

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

from src.db.models import CodeCrunchrBase  # noqa: E402

target_metadata = CodeCrunchrBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations(connectable):
    # Modify the context and let it know what we've got
    context.configure(connection=connectable, target_metadata=target_metadata)

    # Run the migrations
    with context.begin_transaction():
        context.run_migrations()

    # Then we're done ig
    return


async def run_async_migrations():
    url = getenv("DATABASE_URL")
    assert url, "database url isnt set in .env :/"

    connectable = create_async_engine(url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = getenv("DATABASE_URL")
    assert url, "database url isnt set in .env :/"

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # Try to retrieve the connectable from a modified config object thing
    connectable = config.attributes.get("connectable", None)

    # If we already have access to something connectable...
    if connectable is not None:
        run_migrations(connectable)
        return

    # If we don't have access to something connectable
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
