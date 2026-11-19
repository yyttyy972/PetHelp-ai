import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/linchong")


def _load_jwt_secret():
    configured = os.getenv("JWT_SECRET")
    if configured is not None:
        if len(configured) < 32:
            raise RuntimeError("JWT_SECRET must contain at least 32 characters")
        return configured

    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("JWT_SECRET must be explicitly configured in production")

    secret_path = ROOT / ".runtime" / "jwt_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass

    secret = secret_path.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise RuntimeError("Stored JWT_SECRET must contain at least 32 characters")
    return secret


JWT_SECRET = _load_jwt_secret()
COMMUNITY = os.getenv("COMMUNITY_CODE", "linchong-001")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(ROOT / "storage"))).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
