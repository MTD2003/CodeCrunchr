from fastapi.routing import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping_ping() -> str:
    """Returns a simple pong response"""
    return "Pong!"


__all__ = ["router"]
