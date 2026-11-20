"""Deterministic explanations for reasons returned by the matching module."""

from typing import Any


REASON_EXPLANATIONS = {
    "身份已核验": "其身份已完成核验",
    "费用偏好完美匹配": "费用偏好与本次需求匹配",
    "已填写经验自述": "填写了经验自述",
}
LOCATION_EXPLANATIONS = {"同栋优先": "平台会优先考虑同栋帮手"}


def _join_details(details: list[str]) -> str:
    if len(details) == 1:
        return details[0]
    return "，".join(details[:-1]) + "，并" + details[-1]


def explain_match(candidate: dict[str, Any]) -> dict[str, Any]:
    """Explain only the reasons already supplied by the matching module."""
    reasons = list(candidate.get("reasons") or [])
    name = str(candidate.get("display_name") or "这位帮手")

    if not reasons:
        return {
            "explanation": f"暂时无法说明为什么推荐{name}，因为平台没有返回匹配理由。",
            "reasons": reasons,
            "fallback": True,
        }

    details = []
    location_details = []
    has_unknown = False
    for reason in reasons:
        if reason in LOCATION_EXPLANATIONS:
            location_details.append(LOCATION_EXPLANATIONS[reason])
            continue
        detail = REASON_EXPLANATIONS.get(reason)
        if detail is None:
            has_unknown = True
            detail = f"平台返回了匹配条件“{reason}”，但当前解释模块没有对应说明"
        details.append(detail)

    sentences = []
    if details:
        sentences.append(_join_details(details) + "。")
    if location_details:
        prefix = "此外，" if sentences else ""
        sentences.append(prefix + _join_details(location_details) + "。")

    return {
        "explanation": "".join(sentences),
        "reasons": reasons,
        "fallback": has_unknown,
    }
