import json
import unittest
from types import SimpleNamespace

from scripts.run_ai_parse_evaluation import (
    SEMANTIC_JUDGE_PROMPT,
    compare_case,
    judge_semantics,
)


def _case(expected_fields=None, expected_checklist=None):
    return {
        "input": {"text": "请把旺财安全送回家"},
        "annotation": {
            "expected_field_values": expected_fields or {},
            "expected_checklist": expected_checklist or [],
            "required_question_topics": [],
            "question_topics_not_to_ask": [],
            "must_not_infer": [],
        },
    }


def _output(draft=None, questions=None):
    return {"draft": draft or {}, "questions": questions or []}


class AiParseEvaluationTests(unittest.TestCase):
    def test_judge_prompt_does_not_treat_required_topics_as_whitelist(self):
        self.assertIn("不是允许追问主题的完整白名单", SEMANTIC_JUDGE_PROMPT)
        self.assertIn("不等于已经提供 budget", SEMANTIC_JUDGE_PROMPT)

    def test_free_text_difference_is_left_for_semantic_judge(self):
        comparison = compare_case(
            _case({"handover_notes": "门禁由宠主远程开启"}),
            _output({
                "handover_notes": "宠主远程开门禁",
                "checklist_items": [],
            }),
        )

        self.assertEqual(comparison["strict_field_mismatches"], [])
        self.assertEqual(
            comparison["semantic_field_differences"], ["handover_notes"]
        )
        self.assertIsNone(
            comparison["field_checks"]["handover_notes"]["passed"]
        )

    def test_contract_field_difference_remains_strict(self):
        comparison = compare_case(
            _case({"budget": 50}),
            _output({"budget": 60, "checklist_items": []}),
        )

        self.assertEqual(comparison["strict_field_mismatches"], ["budget"])
        self.assertIs(
            comparison["field_checks"]["budget"]["passed"], False
        )

    def test_keyword_can_be_satisfied_by_completion_condition(self):
        expected = [{
            "item_key": "return_pet",
            "pet_id": "pet-1",
            "content_keywords": ["安全送回"],
        }]
        actual = [{
            "item_key": "return_pet",
            "pet_id": "pet-1",
            "content": "完成遛狗",
            "completion_condition": "将旺财安全送回",
        }]
        comparison = compare_case(
            _case(expected_checklist=expected),
            _output({"checklist_items": actual}),
        )

        self.assertEqual(
            comparison["checklist_checks"][0]["checks"][
                "missing_content_keywords"
            ],
            [],
        )

    def test_item_key_and_pet_id_matching_remains_strict(self):
        expected = [{
            "item_key": "return_pet",
            "pet_id": "pet-1",
            "content_keywords": ["送回"],
        }]
        actual = [{
            "item_key": "return_pet",
            "pet_id": "pet-2",
            "content": "送回",
        }]
        comparison = compare_case(
            _case(expected_checklist=expected),
            _output({"checklist_items": actual}),
        )

        self.assertEqual(comparison["strict_checklist_mismatches"], [0])

    def test_semantic_judge_accepts_structured_mock_response(self):
        judge_result = {
            "verdict": "passed",
            "summary": "语义一致",
            "field_review": "同义表达",
            "checklist_review": "一致",
            "question_review": "无需追问",
            "inference_review": "没有擅自推断",
        }
        client = self._mock_client(judge_result)
        comparison = compare_case(_case(), _output({"checklist_items": []}))

        result = judge_semantics(
            client, "mock-model", 3.0, _case(), _output(), comparison
        )

        self.assertEqual(result, judge_result)

    def test_semantic_judge_rejects_invalid_verdict(self):
        invalid = {
            "verdict": "maybe",
            "summary": "",
            "field_review": "",
            "checklist_review": "",
            "question_review": "",
            "inference_review": "",
        }
        client = self._mock_client(invalid)
        comparison = compare_case(_case(), _output({"checklist_items": []}))

        with self.assertRaisesRegex(ValueError, "verdict"):
            judge_semantics(
                client, "mock-model", 3.0, _case(), _output(), comparison
            )

    @staticmethod
    def _mock_client(result):
        def create(**kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(result, ensure_ascii=False)
                        )
                    )
                ]
            )

        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )


if __name__ == "__main__":
    unittest.main()
