"""Local integration entry point; leaves the standard B0 app entry unchanged."""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
from app.main import app
from app.ai.router import router as ai_router
app.router.routes = [route for route in app.router.routes if not (getattr(route, "path", None) == "/api/v0/ai/parse" and "POST" in (getattr(route, "methods", set()) or set()))]
app.include_router(ai_router)
