"""Validation helpers for AI parse responses."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "week9" / "ai-parse-schema.json"


class AIResponseValidationError(ValueError):
    """Raised when an AI response does not match the parse response schema."""


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


_VALIDATOR = Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def validate_ai_response(data: Any) -> None:
    """Validate an AI response, raising a readable error for every violation."""
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda error: list(error.absolute_path))
    if not errors:
        return

    details = []
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{path}: {error.message}")

    raise AIResponseValidationError("AI response schema validation failed: " + "; ".join(details))

