"""Validation helpers for AI parse responses."""

import json
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "week9" / "ai-parse-schema.json"

class AIResponseValidationError(ValueError):
    pass

def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)

_VALIDATOR = Draft202012Validator(_load_schema(), format_checker=FormatChecker())

def validate_ai_response(data: Any) -> None:
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        details = [f"{'.'.join(map(str,e.absolute_path)) or '<root>'}: {e.message}" for e in errors]
        raise AIResponseValidationError("AI response schema validation failed: " + "; ".join(details))
