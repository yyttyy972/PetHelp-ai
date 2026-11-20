"""Small, dependency-free retriever for the business-rules knowledge base."""

from collections import Counter
from math import log
from pathlib import Path
import re


RULES_PATH = Path(__file__).resolve().parent / "knowledge" / "business_rules.md"
REQUIRED_FIELDS = (
    "rule_id",
    "title",
    "content",
    "implementation_status",
    "source_file",
    "source_section",
)
RULE_HEADING = re.compile(r"^###\s+(BR-[A-Z]+-\d+)\s*$")
RULE_FIELD = re.compile(r"^-\s+([a-z_]+):\s*(.*)$")
ASCII_TERM = re.compile(r"[a-z][a-z0-9_]{1,}")
CHINESE_RUN = re.compile(r"[\u3400-\u9fff]+")
QUERY_ALIASES = {
    "超过": "超时",
    "过期": "超时",
    "找帮手": "匹配候选",
    "推荐帮手": "匹配候选",
}
MIN_SCORE = 0.07
MIN_MATCHED_FEATURES = 2
RELATIVE_SCORE_CUTOFF = 0.35


def _clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def load_rules(path: str | Path = RULES_PATH) -> list[dict[str, str]]:
    """Parse each ``### BR-...`` section into one rule dictionary."""
    rules = []
    current = None

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        heading = RULE_HEADING.match(line)
        if heading:
            if current is not None:
                rules.append(current)
            current = {"rule_id": heading.group(1)}
            continue

        field = RULE_FIELD.match(line)
        if current is not None and field:
            current[field.group(1)] = _clean_value(field.group(2))

    if current is not None:
        rules.append(current)

    for rule in rules:
        missing = [field for field in REQUIRED_FIELDS if not rule.get(field)]
        if missing:
            raise ValueError(
                f"Rule {rule.get('rule_id', '<unknown>')} is missing: {', '.join(missing)}"
            )
    return rules


def _features(text: str) -> set[str]:
    normalized = text.lower().replace("`", "")
    features = set(ASCII_TERM.findall(normalized))
    for run in CHINESE_RUN.findall(normalized):
        if len(run) == 1:
            features.add(run)
        for size in (2, 3):
            features.update(run[index : index + size] for index in range(len(run) - size + 1))
    return features


def _expand_question(question: str) -> str:
    additions = [alias for phrase, alias in QUERY_ALIASES.items() if phrase in question]
    if "帮手" in question and ("匹配" in question or "推荐" in question):
        additions.append(
            "匹配调用 候选帮手 基础硬过滤 可用时间 时间冲突 推荐排序 推荐理由"
        )
    return " ".join([question, *additions])


def _score_rule(
    query_features: set[str],
    title_features: set[str],
    body_features: set[str],
    document_frequency: Counter[str],
    rule_count: int,
) -> float:
    query_weight = sum(
        log((rule_count + 1) / (document_frequency.get(term, 0) + 1)) + 1
        for term in query_features
    )
    if not query_weight:
        return 0.0

    matched_weight = 0.0
    for term in query_features:
        weight = log((rule_count + 1) / (document_frequency.get(term, 0) + 1)) + 1
        if term in title_features:
            matched_weight += weight * 1.8
        elif term in body_features:
            matched_weight += weight
    return min(matched_weight / query_weight, 1.0)


def search_rules(question: str, top_k: int = 3) -> list[dict[str, str | float]]:
    """Return relevant rules ordered by score, or an empty list for weak matches."""
    if top_k <= 0 or not question or not question.strip():
        return []

    rules = load_rules()
    query_features = _features(_expand_question(question))
    if not query_features:
        return []

    title_features = [_features(rule["title"]) for rule in rules]
    body_features = [
        _features(" ".join((rule["content"], rule.get("conditions", "")))) for rule in rules
    ]
    searchable_features = [
        title | body for title, body in zip(title_features, body_features)
    ]
    document_frequency = Counter(
        feature for features in searchable_features for feature in features
    )

    results = []
    for rule, title, body in zip(rules, title_features, body_features):
        matched_count = len(query_features & (title | body))
        score = _score_rule(query_features, title, body, document_frequency, len(rules))
        if matched_count >= MIN_MATCHED_FEATURES and score >= MIN_SCORE:
            results.append({**rule, "score": round(score, 4)})

    results.sort(key=lambda item: (-float(item["score"]), str(item["rule_id"])))
    if not results:
        return []

    cutoff = max(MIN_SCORE, float(results[0]["score"]) * RELATIVE_SCORE_CUTOFF)
    return [item for item in results if float(item["score"]) >= cutoff][:top_k]
