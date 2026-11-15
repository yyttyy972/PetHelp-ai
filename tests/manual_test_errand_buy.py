"""Manual test for a complete errand-buy request with the real DeepSeek API."""

import json
from datetime import datetime

from src.ai.parser import parse_request


TEXT = (
    "明天下午四点到五点帮年糕买一袋2千克装的猫粮，预算100元，"
    "送到社区东门，预计需要40分钟，有偿。"
)
REFERENCE_TIME = "2026-11-15T10:00:00+08:00"
TIMEZONE = "Asia/Shanghai"
PET_ID = "11111111-1111-4111-8111-111111111111"
PETS = [
    {
        "id": PET_ID,
        "name": "年糕",
        "species": "cat",
    }
]


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() is not None, f"时间缺少时区信息: {value}"
    return parsed


def main() -> None:
    data = parse_request(
        text=TEXT,
        reference_time=REFERENCE_TIME,
        timezone=TIMEZONE,
        pets=PETS,
    )

    print(json.dumps(data, ensure_ascii=False, indent=2))

    draft = data["draft"]
    questions = data["questions"]

    assert draft["service_type"] == "errand_buy"
    assert PET_ID in draft["pet_ids"]

    window_start = _parse_datetime(draft["window_start"])
    window_end = _parse_datetime(draft["window_end"])
    assert window_start.isoformat().startswith("2026-11-16T16:00:00")
    assert window_end.isoformat().startswith("2026-11-16T17:00:00")
    assert draft["expected_duration_minutes"] == 40

    assert draft["fee_type"] == "paid"
    assert draft["budget"] == 100
    assert draft["location"] is not None
    assert "社区东门" in draft["location"]

    items = draft["checklist_items"]
    assert len(items) >= 2
    assert [item["item_key"] for item in items[:2]] == ["purchase", "delivery"]

    purchase = items[0]
    assert purchase["product_name"] == "猫粮"
    assert purchase["quantity"] == 1
    assert purchase["unit"] == "袋"
    assert any(
        weight in purchase["content"]
        for weight in ("2千克", "2 千克", "2kg", "2 kg", "2公斤", "2 公斤")
    ), "purchase.content 未体现 2 千克装"

    delivery = items[1]
    assert delivery["pet_id"] is None
    assert "社区东门" in delivery["content"]

    assert isinstance(questions, list)

    print("Errand buy test passed!")


if __name__ == "__main__":
    main()
