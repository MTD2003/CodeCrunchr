# CodeCrunchr Backend

The CodeCrunchr backend is built with FastAPI.

---

### Running Locally:

To install the dependencies to run the api:
```sh
# With uv:
uv sync

# With no uv:
python -m pip install .
```

To run the api, use:
```sh
# With uv:
uv run uvicorn src.app:app

# With no uv:
python -m uvicorn src.app:app
```

### Running with Docker:

The backend can also be run with docker compose:

```
docker compose up
```

## Development

You can install development dependencies by running:
```sh
# With uv (it includes dev auto-magically on sync):
uv sync 

# With pip:
python -m pip install .[dev]
```

To run the test suite, **ensure that the development dependencies are installed**, and then run:
```sh
# With uv:
uv run -m pytest

# or:
python -m pytest
```

#### Migrations

The backend uses sqlqalchemy as an ORM and alembic to handle database migrations. The API will automatically apply any pending migrations on startup, to create a new migration, run:
```sh
# with uv:
uv run -m alembic revision -m "<message>" --autogenerate

# or:
python -m alembic revision -m "<message>" --autogenerate

# or:
alembic revision -m "<message>" --autogenerate
```