import unittest

from app.ai.match_explainer import explain_match


def candidate(reasons, **overrides):
    data = {
        "helper_id": "helper-1",
        "display_name": "小王",
        "verification_status": "verified",
        "fee_pref": "paid",
        "service_radius_m": 500,
        "address_tag": "2栋",
        "reasons": reasons,
    }
    data.update(overrides)
    return data


class MatchExplainerTests(unittest.TestCase):
    def test_single_reason(self):
        result = explain_match(candidate(["费用偏好完美匹配"]))

        self.assertFalse(result["fallback"])
        self.assertEqual(result["explanation"], "费用偏好与本次需求匹配。")

    def test_multiple_reasons(self):
        result = explain_match(
            candidate(
                [
                    "身份已核验",
                    "费用偏好完美匹配",
                    "同栋优先",
                    "已填写经验自述",
                ]
            )
        )

        self.assertEqual(
            result["explanation"],
            "其身份已完成核验，费用偏好与本次需求匹配，并填写了经验自述。"
            "此外，平台会优先考虑同栋帮手。",
        )

    def test_verification_is_not_exaggerated(self):
        explanation = explain_match(candidate(["身份已核验"]))["explanation"]

        self.assertEqual(explanation, "其身份已完成核验。")
        self.assertNotIn("服务质量", explanation)
        self.assertNotIn("可靠性", explanation)
        self.assertNotIn("信用良好", explanation)
        self.assertNotIn("服务能力强", explanation)

    def test_service_radius_does_not_create_distance_claim(self):
        explanation = explain_match(
            candidate(["费用偏好完美匹配"], service_radius_m=1)
        )["explanation"]

        self.assertNotIn("距离符合", explanation)
        self.assertNotIn("实际距离满足", explanation)
        self.assertNotIn("1米", explanation)

    def test_empty_reasons_returns_conservative_fallback(self):
        result = explain_match(candidate([]))

        self.assertTrue(result["fallback"])
        self.assertIn("平台没有返回匹配理由", result["explanation"])
        self.assertEqual(result["reasons"], [])

    def test_unknown_reason_is_not_interpreted(self):
        result = explain_match(candidate(["社区活动优先"]))

        self.assertTrue(result["fallback"])
        self.assertIn("社区活动优先", result["explanation"])
        self.assertIn("没有对应说明", result["explanation"])

    def test_original_reasons_are_preserved(self):
        reasons = ["身份已核验", "未知条件", "身份已核验"]

        result = explain_match(candidate(reasons))

        self.assertEqual(result["reasons"], reasons)
        self.assertIsNot(result["reasons"], reasons)


if __name__ == "__main__":
    unittest.main()
