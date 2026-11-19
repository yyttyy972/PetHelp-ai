"""AI configuration loaded from environment variables."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class AIConfig:
    api_key: str | None
    base_url: str
    model: str
    timeout: float


def load_ai_config() -> AIConfig:
    """Read the current AI configuration from the process environment."""
    load_dotenv(PROJECT_ROOT / ".env")

    timeout_value = os.getenv("AI_TIMEOUT", "30")
    try:
        timeout = float(timeout_value)
    except ValueError as exc:
        raise ValueError("AI_TIMEOUT must be a number") from exc

    if timeout <= 0:
        raise ValueError("AI_TIMEOUT must be greater than 0")

    return AIConfig(
        api_key=os.getenv("AI_API_KEY"),
        base_url=os.getenv("AI_BASE_URL", DEFAULT_BASE_URL),
        model=os.getenv("AI_MODEL", DEFAULT_MODEL),
        timeout=timeout,
    )
