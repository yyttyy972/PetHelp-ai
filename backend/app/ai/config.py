"""AI configuration loaded from environment variables."""

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class AIConfig:
    api_key: str | None
    base_url: str | None
    model: str | None
    timeout: float

def load_ai_config() -> AIConfig:
    load_dotenv(PROJECT_ROOT / ".env")
    timeout = float(os.getenv("AI_TIMEOUT", "30"))
    if timeout <= 0:
        raise ValueError("AI_TIMEOUT must be greater than 0")
    return AIConfig(
        api_key=os.getenv("AI_API_KEY"),
        base_url=os.getenv("AI_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("AI_MODEL", "deepseek-chat"),
        timeout=timeout,
    )
