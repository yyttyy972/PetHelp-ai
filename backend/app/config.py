import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/linchong")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must contain at least 32 characters")
COMMUNITY = os.getenv("COMMUNITY_CODE", "linchong-001")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(ROOT / "storage"))).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
