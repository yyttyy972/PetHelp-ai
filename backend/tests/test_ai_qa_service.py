import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.ai.qa_service import (
    NO_COVERAGE_MESSAGE,
    SERVICE_UNAVAILABLE_MESSAGE,
    answer_question,
)


RULE = {
    "rule_id": "BR-BOOK-002",
    "title": "预约确认超时",
    "content": "预约确认超时后，Booking 取消，ServiceRequest 回到 pending_match。",
    "conditions": "Booking 为 pending_confirm 且预留已过期。",
    "implementation_status": "部分实现（惰性检查已实现）",
    "source_file": "backend/docs/状态转换表.md；backend/app/routers/bookings.py",
    "source_section": "确认超时；confirm()",
    "score": 0.9,
}


def config(api_key="test-key"):
    return SimpleNamespace(
        api_key=api_key,
        base_url="https://example.invalid",
        model="deepseek-chat",
        timeout=3,
    )


def response(answer="预约会取消，需求重新进入待匹配状态。[BR-BOOK-002]"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer))]
    )


class QAServiceTests(unittest.TestCase):
    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config")
    @patch("app.ai.qa_service.search_rules")
    def test_answers_with_retrieved_rules(self, search, load_config, openai):
        search.return_value = [RULE]
        load_config.return_value = config()
        openai.return_value.chat.completions.create.return_value = response()

        result = answer_question("预约超时怎么办？")

        self.assertFalse(result["fallback"])
        self.assertIn("预约会取消", result["answer"])
        create_call = openai.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(create_call["model"], "deepseek-chat")
        self.assertIn("只能依据", create_call["messages"][0]["content"])
        self.assertIn("不得把", create_call["messages"][0]["content"])
        self.assertIn("用户问什么就直接回答什么", create_call["messages"][0]["content"])
        self.assertIn("面向普通宠物主人", create_call["messages"][0]["content"])
        self.assertIn("不要主动介绍项目规则变动计划", create_call["messages"][0]["content"])
        self.assertIn("不要添加与用户问题无关的免责声明", create_call["messages"][0]["content"])
        self.assertIn("用户明确询问功能细节", create_call["messages"][0]["content"])
        self.assertIn("BR-BOOK-002", create_call["messages"][1]["content"])
        self.assertIn("部分实现", create_call["messages"][1]["content"])

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config")
    @patch("app.ai.qa_service.search_rules", return_value=[])
    def test_no_results_skips_model(self, search, load_config, openai):
        result = answer_question("今天天气怎么样？")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["answer"], NO_COVERAGE_MESSAGE)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["fallback_reason"], "knowledge_not_found")
        load_config.assert_not_called()
        openai.assert_not_called()

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", return_value=config())
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_model_exception_returns_fallback(self, search, load_config, openai):
        openai.return_value.chat.completions.create.side_effect = TimeoutError("secret")

        result = answer_question("预约超时怎么办？")

        self.assertTrue(result["fallback"])
        self.assertIn(SERVICE_UNAVAILABLE_MESSAGE, result["answer"])
        self.assertIn(RULE["content"], result["answer"])
        self.assertIn(RULE["implementation_status"], result["answer"])
        self.assertEqual(result["fallback_reason"], "ai_error")
        self.assertNotIn("secret", result["answer"])
        self.assertEqual(result["sources"][0]["rule_id"], "BR-BOOK-002")

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", return_value=config(api_key=None))
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_missing_api_key_returns_fallback(self, search, load_config, openai):
        result = answer_question("预约超时怎么办？")

        self.assertTrue(result["fallback"])
        self.assertIn(SERVICE_UNAVAILABLE_MESSAGE, result["answer"])
        self.assertIn(RULE["content"], result["answer"])
        self.assertEqual(result["fallback_reason"], "ai_unavailable")
        openai.assert_not_called()

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", side_effect=ValueError("bad config"))
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_configuration_error_returns_safe_fallback(self, search, load_config, openai):
        result = answer_question("预约超时怎么办？")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["fallback_reason"], "ai_unavailable")
        self.assertNotIn("bad config", result["answer"])
        self.assertIn(RULE["content"], result["answer"])
        openai.assert_not_called()

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", return_value=config())
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_empty_model_response_returns_rule_fallback(self, search, load_config, openai):
        openai.return_value.chat.completions.create.return_value = response("   ")

        result = answer_question("预约超时怎么办？")

        self.assertTrue(result["fallback"])
        self.assertEqual(result["fallback_reason"], "ai_error")
        self.assertIn(RULE["content"], result["answer"])

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", return_value=config())
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_result_contains_complete_sources(self, search, load_config, openai):
        openai.return_value.chat.completions.create.return_value = response()

        source = answer_question("预约超时怎么办？")["sources"][0]

        self.assertEqual(
            source,
            {
                "rule_id": RULE["rule_id"],
                "title": RULE["title"],
                "source_file": RULE["source_file"],
                "source_section": RULE["source_section"],
            },
        )

    @patch("app.ai.qa_service.OpenAI")
    @patch("app.ai.qa_service.load_ai_config", return_value=config())
    @patch("app.ai.qa_service.search_rules", return_value=[RULE])
    def test_model_cannot_replace_program_sources(self, search, load_config, openai):
        openai.return_value.chat.completions.create.return_value = response(
            "请参考不存在的 BR-FAKE-999。"
        )

        result = answer_question("预约超时怎么办？")

        self.assertIn("BR-FAKE-999", result["answer"])
        self.assertEqual([source["rule_id"] for source in result["sources"]], ["BR-BOOK-002"])


if __name__ == "__main__":
    unittest.main()
