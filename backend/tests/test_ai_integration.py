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
from app.ai.router import AIParseRequest, ai_parse, ai_parse as ai_parse_endpoint
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
        self.assertEqual(
            openai.return_value.chat.completions.create.call_args.kwargs["temperature"],
            0,
        )

    @patch("app.ai.parser.load_ai_config")
    @patch("app.ai.parser.OpenAI")
    def test_retries_once_after_schema_validation_failure(self, openai, config):
        selected = [str(uuid4())]
        config.return_value = SimpleNamespace(
            api_key="offline-key",
            base_url="https://example.invalid",
            model="test-model",
            timeout=1,
        )
        invalid = make_draft()
        invalid.pop("questions")
        valid = make_draft()
        openai.return_value.chat.completions.create.side_effect = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content=json.dumps(invalid)),
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content=json.dumps(valid)),
                    )
                ]
            ),
        ]

        result = parse_request(
            text="照顾宠物",
            reference_time="2026-11-16T12:00:00+08:00",
            timezone="Asia/Hong_Kong",
            pets=[],
            selected_pet_ids=selected,
        )

        self.assertEqual(result["draft"]["pet_ids"], selected)
        self.assertEqual(openai.return_value.chat.completions.create.call_count, 2)
        retry_messages = (
            openai.return_value.chat.completions.create.call_args.kwargs["messages"]
        )
        self.assertIn("未通过格式或 Schema 校验", retry_messages[-1]["content"])

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

    @patch("app.ai.router.parse_request")
    def test_omitted_pet_ids_defaults_to_empty_list(self, parser):
        parser.return_value = make_draft("没有指定宠物", [])
        body = AIParseRequest(
            text="帮忙照看宠物",
            reference_time="2026-11-16T12:00:00+08:00",
            timezone="Asia/Hong_Kong",
        )

        result = ai_parse(body, {"id": uuid4()}, None)

        self.assertEqual(body.pet_ids, [])
        self.assertEqual(result["draft"]["pet_ids"], [])
        self.assertEqual(parser.call_args.kwargs["selected_pet_ids"], [])


class RegistrationTests(unittest.TestCase):
    def test_formal_app_has_one_ai_route_and_health(self):
        from app.main import app

        def flattened(routes):
            for route in routes:
                nested = getattr(route, "original_router", None)
                if nested is not None:
                    yield from flattened(nested.routes)
                else:
                    yield route

        matches = [
            route
            for route in flattened(app.routes)
            if getattr(route, "path", None) == "/api/v0/ai/parse"
            and "POST" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0].endpoint, ai_parse_endpoint)
        self.assertIn("/api/v0/ai/parse", app.openapi()["paths"])
        self.assertIn("/health", app.openapi()["paths"])

    def test_standalone_entry_exports_same_formal_app(self):
        from app.main import app
        from run_ai_integration import app as standalone_app

        self.assertIs(standalone_app, app)


if __name__ == "__main__":
    unittest.main()
