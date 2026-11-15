import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


os.environ.setdefault(
    "JWT_SECRET",
    "offline-test-secret-that-is-at-least-32-characters",
)

from app.ai.parser import parse_request
from app.ai.router import AIParseRequest, ai_parse
from app.ai.schema import AIResponseValidationError, validate_ai_response
from app.routers.api import Error


def make_draft(raw_text="model changed this", pet_ids=None):
    return {
        "draft": {
            "pet_ids": pet_ids or [],
            "service_type": "home_visit",
            "fee_type": None,
            "window_start": None,
            "window_end": None,
            "expected_duration_minutes": None,
            "location": None,
            "budget": None,
            "handover_notes": None,
            "emergency_contact": None,
            "requirements": None,
            "precautions": None,
            "raw_text": raw_text,
            "checklist_items": [],
        },
        "questions": ["请补充服务时间。"],
    }


class ParserTests(unittest.TestCase):
    @patch("app.ai.parser.load_ai_config")
    @patch("app.ai.parser.OpenAI")
    def test_preserves_raw_text_and_selected_pets(self, openai, config):
        selected = [str(uuid4()), str(uuid4())]
        config.return_value = SimpleNamespace(
            api_key="offline-key",
            base_url="https://example.invalid",
            model="test-model",
            timeout=1,
        )
        openai.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(make_draft())),
                )
            ]
        )

        result = parse_request(
            text="照顾两只宠物",
            reference_time="2026-11-16T12:00:00+08:00",
            timezone="Asia/Hong_Kong",
            pets=[],
            selected_pet_ids=selected,
        )

        self.assertEqual(result["draft"]["raw_text"], "照顾两只宠物")
        self.assertEqual(result["draft"]["pet_ids"], selected)
        user_message = openai.return_value.chat.completions.create.call_args.kwargs[
            "messages"
        ][1]["content"]
        self.assertEqual(json.loads(user_message)["selected_pet_ids"], selected)

    def test_rejects_checklist_pet_outside_draft(self):
        data = make_draft(raw_text="照顾宠物")
        data["draft"]["checklist_items"] = [
            {
                "item_key": "feed_food",
                "pet_id": str(uuid4()),
                "position": 1,
                "content": "喂食",
                "completion_condition": "完成喂食",
                "required": True,
            }
        ]
        with self.assertRaises(AIResponseValidationError):
            validate_ai_response(data)


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, query, params):
        self.queries.append((query, params))
        row = self.row if params[0] == self.row["id"] else None
        return FakeCursor(row)


class RouteTests(unittest.TestCase):
    @patch("app.ai.router.parse_request")
    def test_passes_owned_pet_profile_without_writing(self, parser):
        pet_id = uuid4()
        owner_id = uuid4()
        pet = {
            "id": pet_id,
            "owner_id": owner_id,
            "name": "豆豆",
            "species": "dog",
            "breed": None,
            "birth_date": "2024-01-01",
            "temperament": "温和",
            "precautions": None,
            "supplies_location": None,
            "care_instructions": None,
        }
        parser.return_value = make_draft("遛豆豆", [str(pet_id)])
        body = AIParseRequest(
            text="遛豆豆",
            reference_time="2026-11-16T12:00:00+08:00",
            timezone="Asia/Hong_Kong",
            pet_ids=[pet_id],
        )
        connection = FakeConnection(pet)

        result = ai_parse(body, {"id": owner_id}, connection)

        self.assertEqual(result["draft"]["pet_ids"], [str(pet_id)])
        self.assertEqual(parser.call_args.kwargs["pets"][0]["name"], "豆豆")
        self.assertTrue(all(query.lstrip().upper().startswith("SELECT") for query, _ in connection.queries))

    @patch("app.ai.router.parse_request")
    def test_rejects_foreign_pet_before_parser(self, parser):
        pet_id = uuid4()
        pet = {
            "id": pet_id,
            "owner_id": uuid4(),
            "name": "豆豆",
            "species": "dog",
            "breed": None,
            "birth_date": "2024-01-01",
            "temperament": None,
            "precautions": None,
            "supplies_location": None,
            "care_instructions": None,
        }
        body = AIParseRequest(
            text="遛豆豆",
            reference_time="2026-11-16T12:00:00+08:00",
            timezone="Asia/Hong_Kong",
            pet_ids=[pet_id],
        )

        with self.assertRaises(Error) as raised:
            ai_parse(body, {"id": uuid4()}, FakeConnection(pet))

        self.assertEqual(raised.exception.status, 403)
        parser.assert_not_called()


class RegistrationTests(unittest.TestCase):
    def test_replaces_only_the_placeholder(self):
        from run_ai_integration import ai_router, app, backend_router

        backend_matches = [
            route
            for route in backend_router.routes
            if getattr(route, "path", None) == "/api/v0/ai/parse"
            and "POST" in getattr(route, "methods", set())
        ]
        ai_matches = [
            route
            for route in ai_router.routes
            if getattr(route, "path", None) == "/api/v0/ai/parse"
            and "POST" in getattr(route, "methods", set())
        ]
        self.assertEqual(backend_matches, [])
        self.assertEqual(len(ai_matches), 1)
        self.assertIn("/api/v0/ai/parse", app.openapi()["paths"])
        self.assertIn("/health", app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
