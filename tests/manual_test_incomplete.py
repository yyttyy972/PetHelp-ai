"""Manual test for parsing an incomplete request with the real DeepSeek API."""

import json

from src.ai.parser import parse_request


TEXT = "帮我遛旺财，明天下午有空就行。"
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


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


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

    assert draft["service_type"] == "dog_walking"
    assert WANGCAI_ID in draft["pet_ids"]
    assert draft["window_start"] is None
    assert draft["window_end"] is None
    assert draft["expected_duration_minutes"] is None
    assert isinstance(questions, list) and questions

    assert any(
        _contains_any(question, ("具体时间", "服务时间", "几点", "时间段", "时段"))
        for question in questions
    ), "questions 中缺少关于具体服务时间的追问"
    assert any(
        _contains_any(question, ("预计时长", "服务时长", "多长时间", "多久", "多少分钟", "几分钟"))
        for question in questions
    ), "questions 中缺少关于预计时长的追问"
    assert any(
    _contains_any(question, ("预算", "金额", "费用上限"))
    for question in questions
    ), "questions 中缺少预算相关追问"

    for field in (
        "fee_type",
        "budget",
        "location",
        "handover_notes",
        "emergency_contact",
        "requirements",
        "precautions",
    ):
        assert draft[field] is None, f"未提供的字段 {field} 不应被自行编造"


if __name__ == "__main__":
    main()
