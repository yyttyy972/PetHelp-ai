"""Validation helpers for AI parse responses."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).resolve().parent / "ai-parse-schema.json"


class AIResponseValidationError(ValueError):
    """Raised when an AI response does not match the parse response schema."""


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


_VALIDATOR = Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def validate_ai_response(
    data: Any,
    *,
    expected_raw_text: str | None = None,
    expected_pet_ids: list[str] | None = None,
) -> None:
    """Validate an AI response, raising a readable error for every violation."""
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda error: list(error.absolute_path))
    details = []
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{path}: {error.message}")

    if not errors:
        draft = data["draft"]
        pet_ids = draft["pet_ids"]
        pet_id_set = set(pet_ids)

        if expected_raw_text is not None and draft["raw_text"] != expected_raw_text:
            details.append("draft.raw_text: must exactly match the user input")
        if expected_pet_ids is not None and pet_ids != expected_pet_ids:
            details.append("draft.pet_ids: must exactly match selected_pet_ids")

        item_keys = []
        for index, item in enumerate(draft["checklist_items"]):
            item_keys.append(item["item_key"])
            if item["pet_id"] is not None and item["pet_id"] not in pet_id_set:
                details.append(
                    f"draft.checklist_items.{index}.pet_id: must belong to draft.pet_ids"
                )
            if item["position"] != index + 1:
                details.append(
                    f"draft.checklist_items.{index}.position: must equal {index + 1}"
                )
        if len(item_keys) != len(set(item_keys)):
            details.append("draft.checklist_items: item_key values must be unique")

        start = draft["window_start"]
        end = draft["window_end"]
        if start is not None and end is not None:
            start_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
            if end_at <= start_at:
                details.append("draft.window_end: must be later than draft.window_start")
            duration = draft["expected_duration_minutes"]
            if duration is not None and (end_at - start_at).total_seconds() < duration * 60:
                details.append(
                    "draft.expected_duration_minutes: must not exceed the time window"
                )

    if not details:
        return

    raise AIResponseValidationError("AI response schema validation failed: " + "; ".join(details))
