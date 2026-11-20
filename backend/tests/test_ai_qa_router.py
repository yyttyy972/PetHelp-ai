import os
import unittest
from unittest.mock import patch


os.environ.setdefault(
    "JWT_SECRET",
    "offline-test-secret-that-is-at-least-32-characters",
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.router import ai_parse, ai_qa, router


QA_RESULT = {
    "answer": "预约会取消，需求重新进入待匹配状态。",
    "sources": [
        {
            "rule_id": "BR-BOOK-002",
            "title": "预约确认超时",
            "source_file": "backend/docs/状态转换表.md",
            "source_section": "确认超时",
        }
    ],
    "fallback": False,
}


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def find_route(path):
    return next(
        route
        for route in router.routes
        if route.path == path and "POST" in route.methods
    )


def flattened(routes):
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from flattened(nested.routes)
        else:
            yield route


class QARouterTests(unittest.TestCase):
    def test_qa_route_is_registered(self):
        from app.main import app

        matches = [
            route
            for route in flattened(app.routes)
            if route.path == "/api/v0/ai/qa" and "POST" in route.methods
        ]

        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0].endpoint, ai_qa)
        self.assertIn("/api/v0/ai/qa", app.openapi()["paths"])

    @patch("app.ai.router.answer_question", return_value=QA_RESULT)
    def test_normal_request_calls_answer_question(self, answer):
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "  预约超过15分钟没有确认怎么办？  "},
        )

        self.assertEqual(response.status_code, 200)
        answer.assert_called_once_with("预约超过15分钟没有确认怎么办？")

    @patch("app.ai.router.answer_question", return_value=QA_RESULT)
    def test_returns_service_result_unchanged(self, answer):
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "预约超时怎么办？"},
        )

        self.assertEqual(response.json(), QA_RESULT)
        self.assertEqual(
            set(response.json()),
            {"answer", "sources", "fallback"},
        )

    @patch("app.ai.router.answer_question")
    def test_empty_question_is_rejected(self, answer):
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "   "},
        )

        self.assertEqual(response.status_code, 422)
        answer.assert_not_called()

    @patch("app.ai.router.answer_question")
    def test_extra_field_is_rejected(self, answer):
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "预约超时怎么办？", "request_id": "forbidden"},
        )

        self.assertEqual(response.status_code, 422)
        answer.assert_not_called()

    @patch("app.ai.router.answer_question")
    def test_question_over_2000_characters_is_rejected(self, answer):
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "问" * 2_001},
        )

        self.assertEqual(response.status_code, 422)
        answer.assert_not_called()

    def test_parse_route_still_registered_once(self):
        matches = [
            route
            for route in router.routes
            if route.path == "/api/v0/ai/parse" and "POST" in route.methods
        ]

        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0].endpoint, ai_parse)

    @patch("app.ai.router.answer_question", return_value=QA_RESULT)
    def test_qa_route_has_no_database_dependency(self, answer):
        route = find_route("/api/v0/ai/qa")

        self.assertEqual(route.dependant.dependencies, [])
        response = make_client().post(
            "/api/v0/ai/qa",
            json={"question": "预约超时怎么办？"},
        )
        self.assertEqual(response.status_code, 200)
        answer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
