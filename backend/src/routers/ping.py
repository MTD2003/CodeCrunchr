from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

router = APIRouter(
    tags=["debug"]
)

@router.get("/ping")
async def ping_ping() -> JSONResponse:
    """
    Returns a simple ping response.

    Mainly meant to be used for ready/liveliness checks
    in the hosted environment.
    """

    return JSONResponse({"api_ok": True})

__all__ = ["router"]
