"""Local entry point that replaces only B's AI placeholder route."""

from fastapi.routing import APIRoute

from app.main import app
from app.routers.api import router as backend_router
from app.ai.router import router as ai_router


def _is_ai_parse_placeholder(route) -> bool:
    return (
        isinstance(route, APIRoute)
        and route.path == "/api/v0/ai/parse"
        and "POST" in route.methods
    )


backend_router.routes[:] = [
    route for route in backend_router.routes if not _is_ai_parse_placeholder(route)
]
app.include_router(ai_router)
app.openapi_schema = None
