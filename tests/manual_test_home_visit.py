
"""Manual test for a complete home-visit request."""

import json

from src.ai.parser import parse_request


TEXT = (
    "明天下午两点到三点来我家，给年糕喂一次猫粮并换水，"
    "猫粮在厨房柜子里，别开阳台门。预计半小时，有偿，预算30元。"
    "地点是春和社区3栋1202室，门禁由我远程开启，"
    "钥匙放在密码钥匙盒。紧急联系人是13800000000。"
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


def main():
    data = parse_request(
        text=TEXT,
        reference_time=REFERENCE_TIME,
        timezone=TIMEZONE,
        pets=PETS,
    )

    print(json.dumps(data, ensure_ascii=False, indent=2))

    draft = data["draft"]
    questions = data["questions"]

    # 1. 服务类型和宠物
    assert draft["service_type"] == "home_visit"
    assert PET_ID in draft["pet_ids"]

    # 2. 时间和时长
    assert draft["window_start"] is not None
    assert draft["window_end"] is not None
    assert "2026-11-16T14:00" in draft["window_start"]
    assert "2026-11-16T15:00" in draft["window_end"]
    assert draft["expected_duration_minutes"] == 30

    # 3. 费用
    assert draft["fee_type"] == "paid"
    assert draft["budget"] == 30

    # 4. 地点和交接信息
    assert draft["location"] is not None
    assert draft["handover_notes"] is not None
    assert draft["emergency_contact"] is not None

    # 5. 照料清单
    items = draft["checklist_items"]
    assert len(items) >= 2

    contents = " ".join(item["content"] for item in items)

    assert "喂" in contents
    #assert "换水" in contents
    assert any(
    item["item_key"] == "change_water"
    for item in items
    ), "未识别出换水任务"
    assert "厨房柜子" in contents

    # 6. 安全注意事项
    assert draft["precautions"] is not None
    assert "阳台" in draft["precautions"]

    # 7. 完整需求不应产生额外补问
    #assert questions == []
    assert isinstance(questions, list)

# 缺少喂食份量时，应该主动追问
    assert any(
        any(keyword in q for keyword in ("份量", "几克", "几勺"))
        for q in questions
    )
    
    print("\nHome visit test passed!")


if __name__ == "__main__":
    main()
