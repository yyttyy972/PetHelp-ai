"""Application-level contract checks for AI drafts before returning them."""
from copy import deepcopy
from datetime import datetime
from typing import Any
from .schema import validate_ai_response

def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("AI time values must include a timezone")
    return parsed

def normalize_ai_result(result: dict[str, Any], selected_pet_ids: list[str], raw_text: str) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("draft"), dict):
        raise ValueError("AI response must contain a draft object")
    normalized = deepcopy(result)
    draft = normalized["draft"]
    selected = [str(x) for x in selected_pet_ids]
    selected_set = set(selected)
    draft["pet_ids"] = selected
    draft["raw_text"] = raw_text
    items = draft.get("checklist_items")
    if not isinstance(items, list):
        raise ValueError("draft.checklist_items must be an array")
    for item in items:
        pet_id = item.get("pet_id")
        if pet_id is not None and str(pet_id) not in selected_set:
            raise ValueError("checklist item references an unselected pet")
    start, end, duration = draft.get("window_start"), draft.get("window_end"), draft.get("expected_duration_minutes")
    if start is not None and end is not None:
        start_dt, end_dt = _parse_datetime(start), _parse_datetime(end)
        if end_dt <= start_dt:
            raise ValueError("window_end must be later than window_start")
        if duration is not None and duration * 60 > (end_dt-start_dt).total_seconds():
            raise ValueError("expected duration exceeds service window")
    validate_ai_response(normalized)
    return normalized
