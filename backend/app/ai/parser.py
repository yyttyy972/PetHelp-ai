"""Public interface for turning natural-language requests into task drafts."""

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import load_ai_config
from .schema import validate_ai_response


PROMPT_PATH = Path(__file__).resolve().parent / "prompt-v3.md"


class AIConfigurationError(RuntimeError):
    """Raised when required AI configuration is missing."""


class AIModelResponseError(RuntimeError):
    """Raised when the model response cannot be safely consumed."""


class AIModelRequestError(RuntimeError):
    """Raised when the configured AI service cannot complete a request."""


def parse_request(
    text: str,
    reference_time: Any,
    timezone: str,
    pets: Any = None,
    selected_pet_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Parse a natural-language request into a schema-validated task draft."""
    config = load_ai_config()
    if not config.api_key or not config.api_key.strip():
        raise AIConfigurationError("AI_API_KEY is missing; configure it before calling the AI model")

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    selected_pet_ids = selected_pet_ids or []
    user_message = json.dumps(
        {
            "text": text,
            "reference_time": reference_time,
            "timezone": timezone,
            "pets": pets,
            "selected_pet_ids": selected_pet_ids,
        },
        ensure_ascii=False,
        default=str,
    )

    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout,
    )
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            timeout=config.timeout,
            max_tokens=4096,
        )
    except Exception as exc:
        raise AIModelRequestError("AI model request failed") from exc

    if not response.choices:
        raise AIModelResponseError("AI model returned no response choices")

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise AIModelResponseError("AI model output was truncated because the token limit was reached")

    content = choice.message.content
    if content is None or not content.strip():
        raise AIModelResponseError("AI model returned empty response content")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIModelResponseError(
            f"AI model returned invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict) or not isinstance(data.get("draft"), dict):
        raise AIModelResponseError("AI model response is missing the draft object")

    # Both values are authoritative caller input, not model decisions.
    data["draft"]["raw_text"] = text
    data["draft"]["pet_ids"] = selected_pet_ids

    validate_ai_response(
        data,
        expected_raw_text=text,
        expected_pet_ids=selected_pet_ids,
    )
    return data
