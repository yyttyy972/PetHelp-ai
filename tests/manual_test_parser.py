"""Manual smoke test for the real DeepSeek parser integration."""

import json
from datetime import datetime

from src.ai.parser import parse_request


TEXT = (
    "明天晚上19:00到20:00帮我遛旺财30分钟，在小区内走。"
    "它看到大型犬会害怕，请保持距离。免费互助，预算0元，"
    "地点在春和社区3栋门口。宠主当面交接牵引装备，"
    "有问题联系13800000000。"
)
REFERENCE_TIME = "2026-11-15T10:00:00+08:00"
TIMEZONE = "Asia/Shanghai"
PETS = [
    {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "旺财",
        "species": "dog",
    }
]
WANGCAI_ID = "22222222-2222-4222-8222-222222222222"


def _has_timezone(value: str) -> bool:
    """Return whether an ISO 8601 datetime contains a UTC offset."""
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except (TypeError, ValueError):
        return False


def main() -> None:
    data = parse_request(
        text=TEXT,
        reference_time=REFERENCE_TIME,
        timezone=TIMEZONE,
        pets=PETS,
    )

    print(json.dumps(data, ensure_ascii=False, indent=2))

    draft = data["draft"]
    assert draft["service_type"] == "dog_walking"
    assert WANGCAI_ID in draft["pet_ids"]
    assert draft["expected_duration_minutes"] == 30
    assert isinstance(data["questions"], list)
    assert [item["item_key"] for item in draft["checklist_items"][:3]] == [
        "pickup",
        "departure",
        "return",
    ]
    assert _has_timezone(draft["window_start"])
    assert _has_timezone(draft["window_end"])


if __name__ == "__main__":
    main()
