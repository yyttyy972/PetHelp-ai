"""Run the annotated AI parse dataset against the real configured model."""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Any
import unicodedata

from openai import OpenAI

from src.ai.config import load_ai_config
from src.ai.parser import parse_request
from src.ai.schema import AIResponseValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "docs" / "week10" / "ai-parse-evaluation-dataset-v1.1.json"
DEFAULT_RESULTS = (
    PROJECT_ROOT / "docs" / "week10" / "ai-parse-evaluation-results-prompt-v1.json"
)
DEFAULT_SOURCE_RESULTS = (
    PROJECT_ROOT / "docs" / "week10" / "ai-parse-evaluation-results-v1.json"
)
DEFAULT_JUDGE_SOURCE_RESULTS = (
    PROJECT_ROOT / "docs" / "week10" / "ai-parse-evaluation-results-prompt-v2.json"
)
DEFAULT_JUDGE_RESULTS = (
    PROJECT_ROOT / "docs" / "week10" / "ai-parse-evaluation-results-prompt-v2-judged.json"
)

JUDGE_SYSTEM_PROMPT = """You are a strict semantic judge for a pet-service parser evaluation.
Review only the supplied natural-language differences. Use raw_text as the source of truth.
Return PASS only when expected and actual preserve all material facts with no conflict.
Return FAIL for a missing key fact, invented fact, contradiction, changed location/party/action,
or changed negation. Return REVIEW only when the evidence is genuinely insufficient.
Do not relax structural fields, identifiers, numbers, times, enum values, checklist keys/order,
required questions, or other deterministic rules. Return one JSON object with this shape:
{"verdict":"PASS|FAIL|REVIEW","reason":"brief reason","items":[{"target":"...","verdict":"PASS|FAIL|REVIEW","reason":"brief reason"}]}.
Every supplied difference must have exactly one items entry with the same target."""

QUESTION_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "time_window": ("时间", "几点", "时段", "开始", "结束"),
    "food_portion": ("份量", "多少克", "几克", "几勺", "刻度"),
    "duration": ("时长", "多久", "多少分钟", "多长时间"),
    "care_items": ("照料", "事项", "需要做", "服务内容"),
    "medicine_instructions": ("药", "用量", "药量", "说明"),
    "handover": ("交接", "门禁", "钥匙", "牵引装备", "领取方式"),
    "supplies_location": ("用品位置", "存放位置", "放在哪里", "放在哪", "哪里"),
    "service_fee_type": ("免费", "有偿", "费用类型", "服务方式"),
    "service_fee_amount": ("服务费", "报酬", "酬劳"),
    "emergency_contact": ("紧急联系人", "联系方式", "联系电话"),
    "duration_window_conflict": ("时长", "时间窗口", "冲突", "超过"),
    "recurring_schedule_scope": (
        "每次",
        "周期",
        "哪几天",
        "重复",
        "日期范围",
        "下周一至周三",
        "分别创建",
        "拆分",
    ),
    "pet_selection": ("哪只", "宠物", "年糕", "旺财", "小橘"),
    "location": ("地点", "地址", "哪里"),
    "product_name": ("商品", "买什么", "名称"),
    "product_detail": ("品牌", "口味", "规格"),
    "quantity_unit": ("数量", "几", "多少", "单位", "袋", "盒"),
    "budget": ("预算", "金额", "费用上限"),
    "delivery_location": ("送到", "配送", "交付", "地址", "地点"),
    "route": ("路线", "怎么走"),
}

NATURAL_LANGUAGE_FIELDS = {"handover_notes", "requirements", "precautions"}
PUNCTUATION = "，。；：！？、,. ;:!?\t\r\n"
FACT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("喂", "喂食", "投喂"),
    ("换水", "更换饮用水", "更换饮水", "饮用水已更换"),
    ("清理猫砂", "清洁猫砂", "猫砂盆清理"),
    ("接到", "接走", "接宠物", "接狗", "交接"),
    ("送回", "交还", "返回", "安全送回"),
    ("遛狗", "遛行", "外出"),
    ("送到", "送至", "送达"),
    ("喝水", "饮水", "给水"),
    ("开始", "出发", "离开"),
    ("牵引绳", "牵引", "牵好"),
    ("避开", "绕开", "远离"),
)
NEGATION_MARKERS = ("不要", "禁止", "无需", "不用", "不得", "严禁", "勿", "不")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary_path.replace(path)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.translate(str.maketrans("", "", PUNCTUATION))


def _reason(category: str, message: str, severity: str = "failed") -> dict[str, str]:
    return {"category": category, "severity": severity, "message": message}


def _question_has_topic(questions: list[str], topic: str) -> bool:
    normalized_questions = [_normalize_text(question) for question in questions]
    for question in normalized_questions:
        if topic == "service_fee_type":
            if (
                ("免费" in question and "有偿" in question)
                or "是否免费" in question
                or "是否有偿" in question
                or "费用类型" in question
                or "服务方式" in question
            ):
                return True
            continue
        if topic == "pet_selection":
            if any(
                phrase in question
                for phrase in ("哪只宠物", "选择宠物", "指定宠物", "关联哪只", "宠物档案")
            ):
                return True
            continue
        if topic in {"location", "delivery_location"}:
            if any(word in question for word in ("存放", "用品", "猫粮", "猫砂", "水碗")):
                continue
            if any(
                phrase in question
                for phrase in (
                    "服务地点",
                    "交接地点",
                    "送达地点",
                    "配送地点",
                    "地点在哪里",
                    "地址是什么",
                    "送到哪里",
                )
            ):
                return True
            continue
        if topic == "food_portion":
            food_context = any(word in question for word in ("喂", "猫粮", "狗粮", "食物"))
            portion = any(word in question for word in QUESTION_TOPIC_KEYWORDS[topic])
            if food_context and portion and not any(word in question for word in ("不要喂", "无需喂")):
                return True
            continue
        if topic == "supplies_location":
            supplies = any(word in question for word in ("用品", "猫粮", "水碗", "猫砂", "药"))
            location = any(word in question for word in ("位置", "哪里", "何处", "存放", "放在"))
            if supplies and location:
                return True
            continue
        if topic == "duration":
            if any(word in question for word in QUESTION_TOPIC_KEYWORDS[topic]):
                return True
            continue
        if topic == "recurring_schedule_scope":
            if any(word in question for word in QUESTION_TOPIC_KEYWORDS[topic]):
                return True
            if "日期" in question and any(word in question for word in ("范围", "哪些", "确认")):
                return True
            continue
        keywords = QUESTION_TOPIC_KEYWORDS.get(topic, (topic,))
        if any(keyword in question for keyword in keywords):
            return True
    return False


def _check_fields(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        status = "failed"
        reason = "字段值不一致"
        if field == "raw_text":
            status = "passed" if actual_value == expected_value else "failed"
            reason = "raw_text 必须逐字一致"
        elif field == "pet_ids" and isinstance(actual_value, list) and isinstance(
            expected_value, list
        ):
            unique = len(actual_value) == len(set(actual_value))
            status = "passed" if unique and set(actual_value) == set(expected_value) else "failed"
            reason = "pet_ids 按无重复集合比较"
        elif isinstance(actual_value, str) and isinstance(expected_value, str):
            if _normalize_text(actual_value) == _normalize_text(expected_value):
                status = "passed"
                reason = "规范化后文本一致"
            elif field in NATURAL_LANGUAGE_FIELDS:
                status = "needs_review"
                reason = "自然语言字段不等价，需核对事实覆盖"
            else:
                reason = "事实字段规范化后仍不一致"
        elif actual_value == expected_value:
            status = "passed"
            reason = "严格值一致"
        checks[field] = {
            "status": status,
            "passed": status == "passed",
            "expected": expected_value,
            "actual": actual_value,
            "reason": reason,
        }
    return checks


def _fact_covered(
    keyword: str,
    text: str,
    item: dict[str, Any],
    draft: dict[str, Any],
    pet_names: dict[str, str],
) -> bool:
    expected = _normalize_text(keyword)
    actual = _normalize_text(text)
    for group in FACT_GROUPS:
        normalized_group = tuple(_normalize_text(term) for term in group)
        if not any(term in expected for term in normalized_group):
            continue
        expected_polarities = _concept_polarities(expected, normalized_group)
        actual_polarities = _concept_polarities(actual, normalized_group)
        if "negative" in expected_polarities:
            return "negative" in actual_polarities
        if "positive" in expected_polarities:
            return "positive" in actual_polarities
    if expected in actual:
        return True
    item_pet_id = item.get("pet_id")
    if item_pet_id and pet_names.get(item_pet_id) == keyword:
        return True
    if item_pet_id is None and keyword in pet_names.values():
        selected_names = [
            name for pet_id, name in pet_names.items() if pet_id in draft.get("pet_ids", [])
        ]
        if len(selected_names) > 1 and any(
            phrase in actual for phrase in ("两只狗", "两只宠物", "两只", "共同")
        ):
            return True
    duration_match = re.fullmatch(r"(\d+)分钟", expected)
    if duration_match and draft.get("expected_duration_minutes") == int(duration_match.group(1)):
        return True
    if "社区东门" in expected and "社区东门" in actual:
        return True
    return False


def _concept_polarities(text: str, group: tuple[str, ...]) -> set[str]:
    """Return positive/negative uses of a concept in normalized Chinese text."""
    polarities: set[str] = set()
    for term in group:
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            prefix = text[max(0, index - 6) : index]
            polarity = (
                "negative"
                if any(prefix.endswith(marker) for marker in NEGATION_MARKERS)
                else "positive"
            )
            polarities.add(polarity)
            start = index + len(term)
    return polarities


def _pet_id_compatible(
    service_type: str,
    expected_pet_id: Any,
    actual_pet_id: Any,
    draft_pet_ids: list[str],
) -> bool:
    if expected_pet_id == actual_pet_id:
        return True
    return (
        service_type == "home_visit"
        and expected_pet_id is None
        and actual_pet_id in draft_pet_ids
    )


def _item_fact_text(item: dict[str, Any], draft: dict[str, Any]) -> str:
    return (
        f"{item.get('content', '')} {item.get('completion_condition', '')} "
        f"{draft.get('requirements') or ''} {draft.get('precautions') or ''}"
    )


def _check_checklist(
    case: dict[str, Any], draft: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    actual_items = draft.get("checklist_items", [])
    expected_items = case["annotation"]["expected_checklist"]
    service_type = case["service_type"]
    pet_names = {pet["id"]: pet["name"] for pet in case["fixture_only_pet_profiles"]}
    checks: list[dict[str, Any]] = []
    reasons: list[dict[str, str]] = []

    for index, item in enumerate(actual_items, start=1):
        if item.get("position") != index:
            reasons.append(
                _reason("checklist_structure", f"checklist_items[{index - 1}].position 不连续")
            )
        item_pet_id = item.get("pet_id")
        if item_pet_id is not None and item_pet_id not in draft.get("pet_ids", []):
            reasons.append(
                _reason("checklist_pet", f"checklist_items[{index - 1}].pet_id 不属于 draft.pet_ids")
            )

    fixed_prefixes = {
        "dog_walking": ("pickup", "departure", "return"),
        "errand_buy": ("purchase", "delivery"),
    }
    for index, expected_key in enumerate(fixed_prefixes.get(service_type, ())):
        actual_key = actual_items[index].get("item_key") if index < len(actual_items) else None
        if actual_key != expected_key:
            reasons.append(
                _reason(
                    "checklist_structure",
                    f"{service_type} 第 {index + 1} 项应为 {expected_key}，实际为 {actual_key}",
                )
            )

    if service_type == "errand_buy" and actual_items:
        purchase = actual_items[0]
        for field in ("product_name", "quantity", "unit"):
            if field not in purchase:
                reasons.append(_reason("missing_required_field", f"purchase 缺少 {field}"))

    unused_indexes = set(range(len(actual_items)))
    unmatched_expected_item_keys: list[str] = []
    for expected in expected_items:
        exact_index = next(
            (
                index
                for index in unused_indexes
                if actual_items[index].get("item_key") == expected["item_key"]
                and _pet_id_compatible(
                    service_type,
                    expected.get("pet_id"),
                    actual_items[index].get("pet_id"),
                    draft.get("pet_ids", []),
                )
            ),
            None,
        )
        matched_index = exact_index
        key_status = "passed"
        if matched_index is None and service_type == "home_visit":
            matched_index = next(
                (
                    index
                    for index in unused_indexes
                    if _pet_id_compatible(
                        service_type,
                        expected.get("pet_id"),
                        actual_items[index].get("pet_id"),
                        draft.get("pet_ids", []),
                    )
                    and all(
                        _fact_covered(
                            fact,
                            _item_fact_text(actual_items[index], draft),
                            actual_items[index],
                            draft,
                            pet_names,
                        )
                        for fact in expected.get("content_keywords", [])
                    )
                ),
                None,
            )
            if matched_index is not None:
                key_status = "needs_review"
        actual = actual_items[matched_index] if matched_index is not None else None
        if actual is None:
            unmatched_expected_item_keys.append(expected["item_key"])
        if matched_index is not None:
            unused_indexes.remove(matched_index)
        combined_text = _item_fact_text(actual, draft) if actual else ""
        missing_facts = [
            fact
            for fact in expected.get("content_keywords", [])
            if not actual or not _fact_covered(fact, combined_text, actual, draft, pet_names)
        ]
        strict_field_mismatches = []
        for field in ("product_name", "quantity", "unit"):
            if field in expected and (actual is None or actual.get(field) != expected[field]):
                strict_field_mismatches.append(field)
        if actual is None or missing_facts or strict_field_mismatches:
            status = "failed"
        else:
            status = key_status
        check = {
            "status": status,
            "passed": status == "passed",
            "expected": expected,
            "matched_index": matched_index,
            "actual_item_key": actual.get("item_key") if actual else None,
            "missing_facts": missing_facts,
            "strict_field_mismatches": strict_field_mismatches,
        }
        checks.append(check)
        if status == "failed":
            reasons.append(
                _reason(
                    "checklist_fact",
                    f"{expected['item_key']} 缺少事实 {missing_facts} 或字段不符 {strict_field_mismatches}",
                )
            )
        elif status == "needs_review":
            reasons.append(
                _reason(
                    "home_visit_item_key",
                    f"home_visit item_key {actual.get('item_key')} 与标注 {expected['item_key']} 不同",
                    "needs_review",
                )
            )

    for index in sorted(unused_indexes):
        actual = actual_items[index]
        if actual.get("item_key") in unmatched_expected_item_keys:
            unmatched_expected_item_keys.remove(actual["item_key"])
            continue
        reasonably_split = False
        if service_type == "home_visit":
            for expected in expected_items:
                if not _pet_id_compatible(
                    service_type,
                    expected.get("pet_id"),
                    actual.get("pet_id"),
                    draft.get("pet_ids", []),
                ):
                    continue
                same_key = actual.get("item_key") == expected.get("item_key")
                facts = expected.get("content_keywords", [])
                fact_match = bool(facts) and all(
                    _fact_covered(
                        fact,
                        _item_fact_text(actual, draft),
                        actual,
                        draft,
                        pet_names,
                    )
                    for fact in facts
                )
                if same_key or fact_match:
                    reasonably_split = True
                    break
        checks.append(
            {
                "status": "passed" if reasonably_split else "failed",
                "passed": reasonably_split,
                "expected": None,
                "matched_index": index,
                "actual_item_key": actual.get("item_key"),
                "missing_facts": [],
                "strict_field_mismatches": [],
                "reason": (
                    "home_visit 合理拆分或多宠物关联"
                    if reasonably_split
                    else "实际清单项无法与任何标注事项对应"
                ),
            }
        )
        if not reasonably_split:
            reasons.append(
                _reason(
                    "unexpected_checklist_item",
                    f"checklist_items[{index}] 为未经标注或用户要求的额外事项: "
                    f"{actual.get('item_key')}",
                )
            )
    return checks, reasons


def _business_reasons(case: dict[str, Any], data: dict[str, Any]) -> list[dict[str, str]]:
    annotation = case["annotation"]
    draft = data["draft"]
    questions = data["questions"]
    reasons: list[dict[str, str]] = []

    if draft.get("raw_text") != case["input"]["text"]:
        reasons.append(_reason("raw_text", "raw_text 未逐字保留用户输入"))

    start = draft.get("window_start")
    end = draft.get("window_end")
    duration = draft.get("expected_duration_minutes")
    if start and end:
        start_at = datetime.fromisoformat(start)
        end_at = datetime.fromisoformat(end)
        if end_at <= start_at:
            reasons.append(_reason("invalid_window", "window_end 不晚于 window_start"))
        if duration is not None and duration > (end_at - start_at).total_seconds() / 60:
            reasons.append(_reason("duration_window_conflict", "时长超过时间窗口"))

    for topic in annotation["required_question_topics"]:
        if not _question_has_topic(questions, topic):
            reasons.append(_reason("missing_question", f"缺少追问主题: {topic}"))
    for topic in annotation["question_topics_not_to_ask"]:
        if _question_has_topic(questions, topic):
            reasons.append(_reason("unnecessary_question", f"不应追问主题: {topic}"))

    expected_fields = annotation["expected_field_values"]
    explicit_topic_fields = {
        "budget": "budget",
        "fee_type": "service_fee_type",
        "expected_duration_minutes": "duration",
        "location": "location",
    }
    for field, topic in explicit_topic_fields.items():
        if expected_fields.get(field) is None:
            continue
        if topic == "duration" and "duration_window_conflict" in annotation[
            "required_question_topics"
        ]:
            continue
        if _question_has_topic(questions, topic):
            reasons.append(_reason("repeated_question", f"已明确 {field}，不应重复追问"))
    if expected_fields.get("pet_ids") and _question_has_topic(questions, "pet_selection"):
        reasons.append(_reason("repeated_question", "已明确 pet_ids，不应重复追问宠物"))
    return reasons


def _evaluate(case: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    draft = data["draft"]
    field_checks = _check_fields(draft, case["annotation"]["expected_field_values"])
    checklist_checks, reasons = _check_checklist(case, draft)
    reasons.extend(_business_reasons(case, data))
    for field, check in field_checks.items():
        if check["status"] != "passed":
            reasons.append(
                _reason(
                    "field_mismatch",
                    f"字段 {field}: {check['reason']}",
                    check["status"],
                )
            )

    override = case["annotation"].get("evaluation_override")
    if override and override.get("status") == "needs_review":
        reasons.append(_reason("evaluation_context", override["reason"], "needs_review"))
        status = "needs_review"
    elif any(reason["severity"] == "failed" for reason in reasons):
        status = "failed"
    elif any(reason["severity"] == "needs_review" for reason in reasons):
        status = "needs_review"
    else:
        status = "passed"
    decision_reasons = reasons or [
        _reason("all_checks_passed", "Schema、字段、清单、业务约束和追问检查均通过", "passed")
    ]
    return {
        "field_checks": field_checks,
        "checklist_checks": checklist_checks,
        "constraint_violations": [
            reason["message"] for reason in reasons if reason["severity"] == "failed"
        ],
        "decision_reasons": decision_reasons,
        "status": status,
    }


def _new_results(dataset: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    return {
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["version"],
        "dataset_path": str(dataset_path.relative_to(PROJECT_ROOT)),
        "started_at": datetime.now().astimezone().isoformat(),
        "completed_at": None,
        "summary": None,
        "results": [],
    }


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(result["status"] for result in results)
    eligible = len(results) - status_counts["needs_review"]
    failure_reasons = Counter(
        reason["category"]
        for result in results
        if result["status"] in {"failed", "error"}
        for reason in result.get("decision_reasons") or []
        if reason["severity"] == "failed"
    )
    by_service: dict[str, dict[str, int]] = {}
    for service_type in ("home_visit", "dog_walking", "errand_buy"):
        service_counts = Counter(
            result["status"] for result in results if result["service_type"] == service_type
        )
        by_service[service_type] = {
            status: service_counts[status]
            for status in ("passed", "failed", "error", "needs_review")
        }
    return {
        "total": len(results),
        "passed": status_counts["passed"],
        "failed": status_counts["failed"],
        "error": status_counts["error"],
        "needs_review": status_counts["needs_review"],
        "schema_invalid": sum(result["schema_valid"] is False for result in results),
        "accuracy_denominator": eligible,
        "pass_rate_excluding_needs_review": (
            round(status_counts["passed"] / eligible, 4) if eligible else None
        ),
        "by_service_type": by_service,
        "failure_reasons": dict(sorted(failure_reasons.items())),
    }


def _judge_candidates(case: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only unresolved natural-language comparisons eligible for LLM review."""
    candidates: list[dict[str, Any]] = []
    for field in sorted(NATURAL_LANGUAGE_FIELDS):
        check = (result.get("field_checks") or {}).get(field)
        if check and check.get("status") == "needs_review":
            candidates.append(
                {
                    "target": f"draft.{field}",
                    "field": field,
                    "expected": check.get("expected"),
                    "actual": check.get("actual"),
                }
            )

    actual_items = (result.get("actual_output") or {}).get("draft", {}).get(
        "checklist_items", []
    )
    for check_index, check in enumerate(result.get("checklist_checks") or []):
        matched_index = check.get("matched_index")
        expected = check.get("expected")
        # Item-key uncertainty is structural and deliberately excluded from Judge.
        if (
            check.get("status") != "needs_review"
            or not isinstance(expected, dict)
            or not isinstance(matched_index, int)
            or matched_index >= len(actual_items)
            or expected.get("item_key") != actual_items[matched_index].get("item_key")
        ):
            continue
        actual_item = actual_items[matched_index]
        candidates.append(
            {
                "target": f"draft.checklist_items[{matched_index}].natural_language",
                "check_index": check_index,
                "expected": {
                    "content_facts": expected.get("content_keywords", []),
                },
                "actual": {
                    "content": actual_item.get("content"),
                    "completion_condition": actual_item.get("completion_condition"),
                },
            }
        )
    return candidates


def _call_judge(
    client: OpenAI,
    model: str,
    timeout: float,
    case: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "service_type": case["service_type"],
        "raw_text": case["input"]["text"],
        "differences": [
            {
                "target": candidate["target"],
                "expected": candidate["expected"],
                "actual": candidate["actual"],
            }
            for candidate in candidates
        ],
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        response_format={"type": "json_object"},
        timeout=timeout,
        max_tokens=1500,
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise ValueError("Judge response was truncated")
    content = choice.message.content
    if not content or not content.strip():
        raise ValueError("Judge returned empty content")
    judgment = json.loads(content)
    valid_verdicts = {"PASS", "FAIL", "REVIEW"}
    if judgment.get("verdict") not in valid_verdicts:
        raise ValueError("Judge returned an invalid verdict")
    expected_targets = {candidate["target"] for candidate in candidates}
    items = judgment.get("items")
    if not isinstance(items, list) or {item.get("target") for item in items} != expected_targets:
        raise ValueError("Judge did not return exactly one item for every target")
    if any(item.get("verdict") not in valid_verdicts for item in items):
        raise ValueError("Judge returned an invalid item verdict")
    return judgment


def _apply_judgment(
    result: dict[str, Any], candidates: list[dict[str, Any]], judgment: dict[str, Any]
) -> None:
    """Apply semantic verdicts without allowing Judge to override hard checks."""
    item_by_target = {item["target"]: item for item in judgment["items"]}
    passed_fields = {
        candidate["field"]
        for candidate in candidates
        if "field" in candidate
        and item_by_target[candidate["target"]]["verdict"] == "PASS"
    }
    remaining: list[dict[str, str]] = []
    for reason in result.get("decision_reasons") or []:
        resolved = reason["category"] == "field_mismatch" and any(
            f"{field}:" in reason["message"] for field in passed_fields
        )
        if not resolved:
            remaining.append(reason)

    for candidate in candidates:
        item = item_by_target[candidate["target"]]
        if item["verdict"] == "PASS":
            if "field" in candidate:
                result["field_checks"][candidate["field"]].update(
                    status="passed", passed=True, reason="LLM Judge confirmed semantic equivalence"
                )
            elif "check_index" in candidate:
                result["checklist_checks"][candidate["check_index"]].update(
                    status="passed", passed=True, reason="LLM Judge confirmed semantic equivalence"
                )
            continue
        severity = "failed" if item["verdict"] == "FAIL" else "needs_review"
        remaining.append(
            _reason(
                "llm_judge_semantic",
                f"{candidate['target']}: {item.get('reason') or judgment.get('reason') or item['verdict']}",
                severity,
            )
        )

    # These are intentionally recomputed from all remaining deterministic and Judge reasons.
    if any(reason["severity"] == "failed" for reason in remaining):
        result["status"] = "failed"
    elif any(reason["severity"] == "needs_review" for reason in remaining):
        result["status"] = "needs_review"
    else:
        result["status"] = "passed"
        remaining = [_reason("all_checks_passed", "Deterministic checks and semantic Judge passed", "passed")]
    result["decision_reasons"] = remaining
    result["constraint_violations"] = [
        reason["message"] for reason in remaining if reason["severity"] == "failed"
    ]


def evaluate_with_judge(dataset_path: Path, source_path: Path, results_path: Path) -> None:
    """Re-evaluate saved outputs and call DeepSeek only for semantic review candidates."""
    dataset = _read_json(dataset_path)
    source = _read_json(source_path)
    source_results = {result["case_id"]: result for result in source["results"]}
    if {case["case_id"] for case in dataset["cases"]} != set(source_results):
        raise ValueError("Dataset and source results contain different case IDs")

    config = load_ai_config()
    if not config.api_key:
        raise RuntimeError("AI_API_KEY is required for Judge mode")
    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=config.timeout)
    results = _new_results(dataset, dataset_path)
    results.update(
        evaluation_mode="llm_judge_saved_outputs",
        source_results_path=str(source_path.relative_to(PROJECT_ROOT)),
        judge_model=config.model,
    )

    for index, case in enumerate(dataset["cases"], start=1):
        source_result = source_results[case["case_id"]]
        actual_output = source_result.get("actual_output")
        if actual_output is None:
            result = dict(source_result)
            result["judge"] = {"called": False, "reason": "No saved actual_output"}
        else:
            evaluation = _evaluate(case, actual_output)
            result = {
                "case_id": case["case_id"],
                "service_type": case["service_type"],
                "status": evaluation["status"],
                "actual_output": actual_output,
                "schema_valid": source_result.get("schema_valid"),
                "field_checks": evaluation["field_checks"],
                "checklist_checks": evaluation["checklist_checks"],
                "constraint_violations": evaluation["constraint_violations"],
                "decision_reasons": evaluation["decision_reasons"],
                "latency_ms": source_result.get("latency_ms"),
                "error": source_result.get("error"),
            }
            candidates = _judge_candidates(case, result) if result["status"] == "needs_review" else []
            if candidates:
                started = time.perf_counter()
                try:
                    judgment = _call_judge(
                        client, config.model, config.timeout, case, candidates
                    )
                    _apply_judgment(result, candidates, judgment)
                    result["judge"] = {
                        "called": True,
                        "latency_ms": round((time.perf_counter() - started) * 1000),
                        "candidates": [candidate["target"] for candidate in candidates],
                        **judgment,
                    }
                except Exception as exc:
                    result["judge"] = {
                        "called": True,
                        "error": f"{type(exc).__name__}: {exc}",
                        "candidates": [candidate["target"] for candidate in candidates],
                    }
                    result["decision_reasons"].append(
                        _reason("llm_judge_error", str(exc), "needs_review")
                    )
            else:
                result["judge"] = {
                    "called": False,
                    "reason": "No eligible natural-language needs_review difference",
                }
        results["results"].append(result)
        results["summary"] = _summary(results["results"])
        _write_json(results_path, results)
        print(f"[{index}/{len(dataset['cases'])}] {case['case_id']}: {result['status']}", flush=True)

    results["completed_at"] = datetime.now().astimezone().isoformat()
    results["summary"] = _summary(results["results"])
    _write_json(results_path, results)
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2), flush=True)


def run(dataset_path: Path, results_path: Path, resume: bool) -> None:
    dataset = _read_json(dataset_path)
    if len(dataset["cases"]) != dataset["counts"]["total"]:
        raise ValueError("Dataset case count does not match counts.total")

    results = _read_json(results_path) if resume and results_path.exists() else _new_results(
        dataset, dataset_path
    )
    completed_ids = {result["case_id"] for result in results["results"]}

    for index, case in enumerate(dataset["cases"], start=1):
        if case["case_id"] in completed_ids:
            continue
        started = time.perf_counter()
        result: dict[str, Any] = {
            "case_id": case["case_id"],
            "service_type": case["service_type"],
            "status": "error",
            "actual_output": None,
            "schema_valid": None,
            "field_checks": None,
            "checklist_checks": None,
            "constraint_violations": None,
            "decision_reasons": None,
            "latency_ms": None,
            "error": None,
        }
        try:
            data = parse_request(
                text=case["input"]["text"],
                reference_time=case["input"]["reference_time"],
                timezone=case["input"]["timezone"],
                pets=case["fixture_only_pet_profiles"],
            )
            evaluation = _evaluate(case, data)
            result.update(
                actual_output=data,
                schema_valid=True,
                field_checks=evaluation["field_checks"],
                checklist_checks=evaluation["checklist_checks"],
                constraint_violations=evaluation["constraint_violations"],
                decision_reasons=evaluation["decision_reasons"],
                status=evaluation["status"],
            )
        except AIResponseValidationError as exc:
            result.update(
                schema_valid=False,
                error=f"{type(exc).__name__}: {exc}",
                decision_reasons=[
                    _reason("schema_validation", "AI 输出未通过 JSON Schema")
                ],
            )
        except Exception as exc:  # Keep the remaining cases running and record the failure.
            result["error"] = f"{type(exc).__name__}: {exc}"
            result["decision_reasons"] = [
                _reason("runtime_error", f"{type(exc).__name__}: {exc}")
            ]
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        results["results"].append(result)
        results["summary"] = _summary(results["results"])
        _write_json(results_path, results)
        print(
            f"[{index}/{len(dataset['cases'])}] {case['case_id']}: {result['status']} "
            f"({result['latency_ms']} ms)",
            flush=True,
        )

    results["completed_at"] = datetime.now().astimezone().isoformat()
    results["summary"] = _summary(results["results"])
    _write_json(results_path, results)
    print(json.dumps(results["summary"], ensure_ascii=False), flush=True)


def reevaluate_offline(dataset_path: Path, source_path: Path, results_path: Path) -> None:
    """Re-evaluate saved outputs without making model requests."""
    dataset = _read_json(dataset_path)
    source = _read_json(source_path)
    cases = {case["case_id"]: case for case in dataset["cases"]}
    source_results = {result["case_id"]: result for result in source["results"]}
    if set(cases) != set(source_results):
        raise ValueError("Dataset and source results contain different case IDs")

    results = _new_results(dataset, dataset_path)
    results.update(
        evaluation_mode="offline_reassessment",
        source_results_path=str(source_path.relative_to(PROJECT_ROOT)),
        started_at=datetime.now().astimezone().isoformat(),
    )
    for case in dataset["cases"]:
        source_result = source_results[case["case_id"]]
        result: dict[str, Any] = {
            "case_id": case["case_id"],
            "service_type": case["service_type"],
            "status": "error",
            "actual_output": source_result.get("actual_output"),
            "schema_valid": source_result.get("schema_valid"),
            "field_checks": None,
            "checklist_checks": None,
            "constraint_violations": None,
            "decision_reasons": None,
            "latency_ms": source_result.get("latency_ms"),
            "error": source_result.get("error"),
        }
        if result["actual_output"] is not None:
            evaluation = _evaluate(case, result["actual_output"])
            result.update(
                field_checks=evaluation["field_checks"],
                checklist_checks=evaluation["checklist_checks"],
                constraint_violations=evaluation["constraint_violations"],
                decision_reasons=evaluation["decision_reasons"],
                status=evaluation["status"],
            )
        elif result["schema_valid"] is False:
            result["decision_reasons"] = [
                _reason("schema_validation", "保存的 AI 输出未通过 JSON Schema")
            ]
            result["constraint_violations"] = ["保存的 AI 输出未通过 JSON Schema"]
        else:
            result["decision_reasons"] = [
                _reason("runtime_error", result["error"] or "没有可供离线评估的输出")
            ]
            result["constraint_violations"] = [
                result["error"] or "没有可供离线评估的输出"
            ]
        results["results"].append(result)

    results["completed_at"] = datetime.now().astimezone().isoformat()
    results["summary"] = _summary(results["results"])
    _write_json(results_path, results)
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--source-results", type=Path, default=DEFAULT_SOURCE_RESULTS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--judge", action="store_true")
    parser.add_argument(
        "--judge-source-results", type=Path, default=DEFAULT_JUDGE_SOURCE_RESULTS
    )
    parser.add_argument("--judge-results", type=Path, default=DEFAULT_JUDGE_RESULTS)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.judge:
        evaluate_with_judge(
            args.dataset.resolve(),
            args.judge_source_results.resolve(),
            args.judge_results.resolve(),
        )
    elif args.offline:
        reevaluate_offline(
            args.dataset.resolve(), args.source_results.resolve(), args.results.resolve()
        )
    else:
        run(args.dataset.resolve(), args.results.resolve(), args.resume)


if __name__ == "__main__":
    main()
