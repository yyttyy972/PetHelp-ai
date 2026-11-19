import unittest

from app.ai.retriever import load_rules, search_rules


class RuleLoadingTests(unittest.TestCase):
    def test_loads_rules_with_required_fields(self):
        rules = load_rules()

        self.assertGreaterEqual(len(rules), 20)
        required = {
            "rule_id",
            "title",
            "content",
            "implementation_status",
            "source_file",
            "source_section",
        }
        self.assertTrue(all(required <= rule.keys() for rule in rules))
        self.assertEqual(len(rules), len({rule["rule_id"] for rule in rules}))


class RuleSearchTests(unittest.TestCase):
    def test_finds_booking_timeout_rule(self):
        results = search_rules("预约确认超时后怎么办？")

        self.assertTrue(results)
        self.assertEqual(results[0]["rule_id"], "BR-BOOK-002")

    def test_finds_owner_cancellation_rule(self):
        results = search_rules("宠主如何主动取消整个需求？")

        self.assertTrue(results)
        self.assertEqual(results[0]["rule_id"], "BR-BOOK-003")

    def test_finds_matching_rules(self):
        results = search_rules("系统怎样匹配和推荐合适的帮手？", top_k=5)

        self.assertTrue(results)
        self.assertTrue(any(item["rule_id"].startswith("BR-MATCH-") for item in results))

    def test_results_keep_source_information(self):
        result = search_rules("遛狗需要哪些执行记录？", top_k=1)[0]

        self.assertTrue(result["source_file"])
        self.assertTrue(result["source_section"])
        self.assertGreater(result["score"], 0)

    def test_unrelated_question_returns_empty_list(self):
        self.assertEqual(search_rules("如何计算火星到地球的轨道距离？"), [])

    def test_top_k_limits_results(self):
        results = search_rules("预约匹配确认取消规则", top_k=2)

        self.assertTrue(results)
        self.assertLessEqual(len(results), 2)
        self.assertEqual(search_rules("预约匹配确认取消规则", top_k=0), [])

    def test_matching_question_only_returns_matching_rules(self):
        results = search_rules("帮手是如何匹配的？", top_k=5)

        self.assertTrue(results)
        self.assertTrue(all(item["rule_id"].startswith("BR-MATCH-") for item in results))

    def test_high_confidence_cancellation_filters_weak_results(self):
        results = search_rules("宠主主动取消需求会怎么样？", top_k=5)

        self.assertEqual([item["rule_id"] for item in results], ["BR-BOOK-003"])

    def test_timeout_keeps_relevant_confirmation_rules(self):
        results = search_rules("预约超时没有确认怎么办？", top_k=5)
        rule_ids = [item["rule_id"] for item in results]

        self.assertEqual(rule_ids[0], "BR-BOOK-002")
        self.assertIn("BR-BOOK-001", rule_ids)
        self.assertNotIn("BR-MATCH-005", rule_ids)

    def test_withdrawal_comparison_keeps_both_core_rules(self):
        results = search_rules("宠主撤回预约和取消整个需求有什么区别？", top_k=5)

        self.assertEqual(
            [item["rule_id"] for item in results],
            ["BR-BOOK-004", "BR-BOOK-003"],
        )

    def test_weather_question_returns_empty_list(self):
        self.assertEqual(search_rules("今天天气怎么样？"), [])


if __name__ == "__main__":
    unittest.main()
