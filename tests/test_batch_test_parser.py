"""Regression tests for the calibrated offline evaluator."""

import unittest

from tests.batch_test_parser import (
    _apply_judgment,
    _check_checklist,
    _check_fields,
    _fact_covered,
    _judge_candidates,
    _normalize_text,
)


PET_1 = "11111111-1111-4111-8111-111111111111"
PET_2 = "33333333-3333-4333-8333-333333333333"


def _item(item_key: str, position: int, pet_id=None, content="测试事项"):
    return {
        "item_key": item_key,
        "pet_id": pet_id,
        "position": position,
        "content": content,
        "completion_condition": "事项已完成",
        "required": True,
    }


def _case(service_type: str, expected_checklist):
    return {
        "service_type": service_type,
        "fixture_only_pet_profiles": [
            {"id": PET_1, "name": "年糕", "species": "cat"},
            {"id": PET_2, "name": "小橘", "species": "cat"},
        ],
        "annotation": {"expected_checklist": expected_checklist},
    }


def _draft(items, pet_ids=None):
    return {
        "pet_ids": pet_ids or [PET_1],
        "requirements": None,
        "precautions": None,
        "expected_duration_minutes": None,
        "checklist_items": items,
    }


class NegationFactTests(unittest.TestCase):
    def test_positive_feeding_does_not_satisfy_negative_fact(self):
        self.assertFalse(
            _fact_covered(
                "不要喂食",
                "正常喂食",
                _item("feed_food", 1, PET_1),
                _draft([]),
                {PET_1: "年糕"},
            )
        )

    def test_negative_feeding_synonyms_are_accepted(self):
        for actual in ("禁止喂食", "无需投喂"):
            with self.subTest(actual=actual):
                self.assertTrue(
                    _fact_covered(
                        "不要喂食",
                        actual,
                        _item("feed_food", 1, PET_1),
                        _draft([]),
                        {PET_1: "年糕"},
                    )
                )

    def test_negative_feeding_does_not_satisfy_positive_fact(self):
        self.assertFalse(
            _fact_covered(
                "喂食",
                "不要喂食",
                _item("feed_food", 1, PET_1),
                _draft([]),
                {PET_1: "年糕"},
            )
        )


class ExtraChecklistItemTests(unittest.TestCase):
    def test_unrequested_home_visit_item_fails(self):
        case = _case(
            "home_visit",
            [{"item_key": "change_water", "pet_id": PET_1, "content_keywords": ["换水"]}],
        )
        draft = _draft(
            [
                _item("change_water", 1, PET_1, "给年糕换水"),
                _item("feed_food", 2, PET_1, "给年糕喂食"),
            ]
        )
        _, reasons = _check_checklist(case, draft)
        self.assertIn("unexpected_checklist_item", {reason["category"] for reason in reasons})

    def test_reasonable_home_visit_multi_pet_split_passes(self):
        case = _case(
            "home_visit",
            [{"item_key": "change_water", "pet_id": None, "content_keywords": ["换水"]}],
        )
        draft = _draft(
            [
                _item("change_water", 1, PET_1, "给年糕换水"),
                _item("change_water", 2, PET_2, "给小橘换水"),
            ],
            [PET_1, PET_2],
        )
        checks, reasons = _check_checklist(case, draft)
        self.assertTrue(all(check["status"] == "passed" for check in checks))
        self.assertNotIn("unexpected_checklist_item", {reason["category"] for reason in reasons})

    def test_extra_dog_walking_item_fails(self):
        expected = [
            {"item_key": "pickup", "pet_id": PET_1, "content_keywords": []},
            {"item_key": "departure", "pet_id": PET_1, "content_keywords": []},
            {"item_key": "return", "pet_id": PET_1, "content_keywords": []},
        ]
        case = _case("dog_walking", expected)
        draft = _draft(
            [
                _item("pickup", 1, PET_1),
                _item("departure", 2, PET_1),
                _item("return", 3, PET_1),
                _item("feed_food", 4, PET_1, "未经要求的喂食"),
            ]
        )
        _, reasons = _check_checklist(case, draft)
        self.assertIn("unexpected_checklist_item", {reason["category"] for reason in reasons})

    def test_expected_item_with_wrong_pet_is_not_mislabeled_as_extra(self):
        case = _case(
            "errand_buy",
            [
                {
                    "item_key": "purchase",
                    "pet_id": PET_1,
                    "content_keywords": [],
                    "product_name": None,
                    "quantity": None,
                    "unit": None,
                },
                {"item_key": "delivery", "pet_id": None, "content_keywords": []},
            ],
        )
        purchase = _item("purchase", 1, None)
        purchase.update(product_name=None, quantity=None, unit=None)
        draft = _draft([purchase, _item("delivery", 2, None)])
        _, reasons = _check_checklist(case, draft)
        categories = {reason["category"] for reason in reasons}
        self.assertIn("checklist_fact", categories)
        self.assertNotIn("unexpected_checklist_item", categories)


class ExistingCalibrationRegressionTests(unittest.TestCase):
    def test_pet_ids_are_compared_as_a_set(self):
        check = _check_fields({"pet_ids": [PET_2, PET_1]}, {"pet_ids": [PET_1, PET_2]})
        self.assertTrue(check["pet_ids"]["passed"])

    def test_text_normalization_ignores_spacing_and_terminal_punctuation(self):
        self.assertEqual(_normalize_text(" 门禁远程开启。 "), _normalize_text("门禁远程开启"))


class LLMJudgeBoundaryTests(unittest.TestCase):
    def _semantic_result(self):
        return {
            "status": "needs_review",
            "actual_output": {"draft": {"checklist_items": []}},
            "field_checks": {
                "precautions": {
                    "status": "needs_review",
                    "passed": False,
                    "expected": "不要打开阳台门",
                    "actual": "禁止打开阳台门",
                    "reason": "semantic review",
                }
            },
            "checklist_checks": [],
            "decision_reasons": [
                {
                    "category": "field_mismatch",
                    "severity": "needs_review",
                    "message": "字段 precautions: semantic review",
                }
            ],
            "constraint_violations": [],
        }

    def test_semantic_pass_resolves_only_eligible_review(self):
        case = {"service_type": "home_visit", "input": {"text": "别开阳台门"}}
        result = self._semantic_result()
        candidates = _judge_candidates(case, result)
        _apply_judgment(
            result,
            candidates,
            {
                "verdict": "PASS",
                "reason": "same prohibition",
                "items": [{"target": "draft.precautions", "verdict": "PASS", "reason": "same prohibition"}],
            },
        )
        self.assertEqual(result["status"], "passed")

    def test_semantic_fail_becomes_failed(self):
        case = {"service_type": "home_visit", "input": {"text": "不要喂食"}}
        result = self._semantic_result()
        result["field_checks"]["precautions"].update(expected="不要喂食", actual="正常喂食")
        candidates = _judge_candidates(case, result)
        _apply_judgment(
            result,
            candidates,
            {
                "verdict": "FAIL",
                "reason": "opposite meaning",
                "items": [{"target": "draft.precautions", "verdict": "FAIL", "reason": "opposite meaning"}],
            },
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("llm_judge_semantic", {reason["category"] for reason in result["decision_reasons"]})

    def test_judge_pass_cannot_override_hard_failure(self):
        case = {"service_type": "home_visit", "input": {"text": "别开阳台门"}}
        result = self._semantic_result()
        result["decision_reasons"].append(
            {"category": "checklist_structure", "severity": "failed", "message": "fixed key mismatch"}
        )
        candidates = _judge_candidates(case, result)
        _apply_judgment(
            result,
            candidates,
            {
                "verdict": "PASS",
                "reason": "same meaning",
                "items": [{"target": "draft.precautions", "verdict": "PASS", "reason": "same meaning"}],
            },
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("checklist_structure", {reason["category"] for reason in result["decision_reasons"]})


if __name__ == "__main__":
    unittest.main()
