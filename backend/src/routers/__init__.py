from .ping import router as ping_router
from .users import router as user_router
from .durations import router as duration_router
from .leaderboards import router as leaderboard_router
from .preferences import router as preferences_router

__all__ = ["ping_router", "user_router", "duration_router", "leaderboard_router", "preferences_router"]
