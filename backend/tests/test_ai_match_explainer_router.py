import os
import unittest
from unittest.mock import patch


os.environ.setdefault(
    "JWT_SECRET",
    "offline-test-secret-that-is-at-least-32-characters",
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.router import ai_explain_match, router


CANDIDATE = {
    "helper_id": "helper-1",
    "display_name": "小王",
    "avatar_url": None,
    "verification_status": "verified",
    "fee_pref": "paid",
    "service_radius_m": 500,
    "address_tag": "2栋",
    "reasons": ["身份已核验", "同栋优先"],
}

EXPLANATION = {
    "explanation": "推荐小王，是因为身份状态已核验，并且平台返回了同栋优先条件。",
    "reasons": ["身份已核验", "同栋优先"],
    "fallback": False,
}


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def find_route():
    return next(
        route
        for route in router.routes
        if route.path == "/api/v0/ai/explain-match" and "POST" in route.methods
    )


def flattened(routes):
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from flattened(nested.routes)
        else:
            yield route


class MatchExplainerRouterTests(unittest.TestCase):
    def test_route_is_registered(self):
        from app.main import app

        matches = [
            route
            for route in flattened(app.routes)
            if route.path == "/api/v0/ai/explain-match" and "POST" in route.methods
        ]

        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0].endpoint, ai_explain_match)
        self.assertIn("/api/v0/ai/explain-match", app.openapi()["paths"])

    @patch("app.ai.router.explain_match", return_value=EXPLANATION)
    def test_route_calls_explainer_and_returns_result(self, explain):
        response = make_client().post(
            "/api/v0/ai/explain-match",
            json={"candidate": CANDIDATE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), EXPLANATION)
        explain.assert_called_once_with(CANDIDATE)

    @patch("app.ai.router.explain_match", return_value=EXPLANATION)
    def test_route_has_no_database_or_auth_dependency(self, explain):
        route = find_route()

        self.assertEqual(route.dependant.dependencies, [])
        response = make_client().post(
            "/api/v0/ai/explain-match",
            json={"candidate": CANDIDATE},
        )
        self.assertEqual(response.status_code, 200)
        explain.assert_called_once()

    @patch("app.ai.router.explain_match")
    def test_missing_candidate_is_rejected(self, explain):
        response = make_client().post("/api/v0/ai/explain-match", json={})

        self.assertEqual(response.status_code, 422)
        explain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
