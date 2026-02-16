from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from ..db import get_session
from sqlalchemy import literal, select


router = APIRouter()


@router.get("/ping")
async def ping_ping() -> JSONResponse:
    """
    Returns a ping response, and also checks to see if
    the database is working.
    """

    # uber simple "SELECT 1" query to test db connectivity
    async with get_session() as session:
        res = await session.execute(select(literal(1)))

    # return a juicy json response with both true values (fingers-crossed)
    return JSONResponse({"api_ok": True, "db_ok": res.scalar_one() == 1})


__all__ = ["router"]
