"""RAG question answering over the local business-rules knowledge base."""

from typing import Any

from openai import OpenAI

from .config import load_ai_config
from .retriever import search_rules


SYSTEM_PROMPT = """你是邻宠帮业务规则问答助手。
只能依据用户消息中提供的业务规则回答，不得使用规则之外的推测。
不得编造业务流程、状态、权限、接口或实现情况。
不得把“未实现”“部分实现”或“待确认”的功能描述为已经实现。
你只能解释规则，不得自行创建、修改或推进任何业务状态。
用户问什么就直接回答什么，第一句应直接给出结论。
请面向普通宠物主人，使用简洁、自然的中文和“需求”“预约”“待匹配”等日常表达。
不要主动介绍项目规则变动计划、跨组待确认事项、数据库实现、定时任务或内部限制。
不要添加与用户问题无关的免责声明，不重复来源文件路径，也不要大量堆砌规则编号。
除非用户明确询问功能或技术细节，否则不要主动使用 ServiceRequest、Booking、
pending_match、reserved_until、create()、confirm() 等内部字段、状态值或函数名。
用户明确询问功能细节时，仍须依据提供的真实规则回答；信息不足以回答时应如实说明。
表达可以自然，但不得改变规则原意；涉及未实现功能时必须明确说尚未实现。"""

NO_COVERAGE_MESSAGE = (
    "目前的规则库还没有覆盖这个问题，你可以查看平台规则或联系工作人员确认。"
)
SERVICE_UNAVAILABLE_MESSAGE = "AI解释服务暂时不可用，下面展示的是平台已记录的相关规则。"


def _sources(rules: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "rule_id": str(rule["rule_id"]),
            "title": str(rule["title"]),
            "source_file": str(rule["source_file"]),
            "source_section": str(rule["source_section"]),
        }
        for rule in rules
    ]


def _context(rules: list[dict[str, Any]]) -> str:
    sections = []
    for rule in rules:
        sections.append(
            "\n".join(
                (
                    f"规则编号：{rule['rule_id']}",
                    f"标题：{rule['title']}",
                    f"正文：{rule['content']}",
                    f"实现状态：{rule['implementation_status']}",
                    f"来源文件：{rule['source_file']}",
                    f"来源章节：{rule['source_section']}",
                )
            )
        )
    return "\n\n---\n\n".join(sections)


def _rule_fallback_answer(rules: list[dict[str, Any]]) -> str:
    summaries = []
    for rule in rules:
        summaries.append(
            f"《{rule['title']}》：{rule['content']} 实现状态：{rule['implementation_status']}。"
        )
    return SERVICE_UNAVAILABLE_MESSAGE + "\n\n" + "\n".join(summaries)


def _fallback(
    rules: list[dict[str, Any]],
    sources: list[dict[str, str]],
    reason: str,
) -> dict[str, Any]:
    return {
        "answer": _rule_fallback_answer(rules),
        "sources": sources,
        "fallback": True,
        "fallback_reason": reason,
    }


def answer_question(question: str) -> dict[str, Any]:
    """Answer from retrieved rules, with safe fallbacks for missing coverage or AI."""
    rules = search_rules(question)
    if not rules:
        return {
            "answer": NO_COVERAGE_MESSAGE,
            "sources": [],
            "fallback": True,
            "fallback_reason": "knowledge_not_found",
        }

    sources = _sources(rules)
    try:
        config = load_ai_config()
    except Exception:
        return _fallback(rules, sources, "ai_unavailable")

    if not config.api_key or not config.api_key.strip():
        return _fallback(rules, sources, "ai_unavailable")

    user_message = f"问题：{question}\n\n可用业务规则：\n{_context(rules)}"
    try:
        client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            timeout=config.timeout,
            max_tokens=1200,
        )
        if not response.choices:
            return _fallback(rules, sources, "ai_error")
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            return _fallback(rules, sources, "ai_error")
    except Exception:
        return _fallback(rules, sources, "ai_error")

    return {"answer": answer.strip(), "sources": sources, "fallback": False}
