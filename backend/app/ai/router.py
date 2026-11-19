"""FastAPI routes for AI request parsing and rule-based question answering."""

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.parser import (
    AIConfigurationError,
    AIModelRequestError,
    AIModelResponseError,
    parse_request,
)
from app.ai.match_explainer import explain_match
from app.ai.qa_service import answer_question
from app.ai.schema import AIResponseValidationError
from app.routers.api import Error, db, me


router = APIRouter(prefix="/api/v0")


class AIParseRequest(BaseModel):
    """Validated request body kept independent from B's shared schemas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=10_000)
    reference_time: AwareDatetime
    timezone: str = Field(min_length=1, max_length=100)
    pet_ids: list[UUID] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_unique_pets(self):
        if len(self.pet_ids) != len(set(self.pet_ids)):
            raise ValueError("duplicate pet_ids")
        return self


class AIQARequest(BaseModel):
    """Validated rule question; no business entity or state is accepted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2_000)


class MatchCandidate(BaseModel):
    """Candidate fields returned by the matching module."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    helper_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    avatar_url: str | None = None
    verification_status: str | None = None
    fee_pref: str | None = None
    service_radius_m: int | None = Field(default=None, ge=0)
    address_tag: str | None = None
    reasons: list[str]


class AIMatchExplanationRequest(BaseModel):
    """Validated wrapper for an existing match candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate: MatchCandidate


PET_PROFILE_FIELDS = (
    "id",
    "name",
    "species",
    "breed",
    "birth_date",
    "temperament",
    "precautions",
    "supplies_location",
    "care_instructions",
)


def _json_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


@router.post("/ai/parse")
def ai_parse(body: AIParseRequest, user=Depends(me), connection=Depends(db)):
    """Parse a draft only; this endpoint performs no database writes."""
    selected_pet_ids = []
    pet_profiles = []

    for pet_id in body.pet_ids:
        pet = connection.execute(
            'SELECT * FROM "PetProfile" WHERE id=%s AND deleted_at IS NULL',
            (pet_id,),
        ).fetchone()
        if pet is None:
            raise Error(404, "not_found")
        if pet["owner_id"] != user["id"]:
            raise Error(403, "forbidden")

        selected_pet_ids.append(str(pet_id))
        pet_profiles.append(
            {field: _json_value(pet[field]) for field in PET_PROFILE_FIELDS}
        )

    try:
        result = parse_request(
            text=body.text,
            reference_time=body.reference_time.isoformat(),
            timezone=body.timezone,
            pets=pet_profiles,
            selected_pet_ids=selected_pet_ids,
        )
    except AIConfigurationError as exc:
        raise Error(503, "ai_unavailable", str(exc)) from exc
    except AIModelRequestError as exc:
        raise Error(502, "ai_upstream_error") from exc
    except (AIModelResponseError, AIResponseValidationError) as exc:
        raise Error(502, "ai_invalid_response") from exc

    return {"draft": result["draft"], "questions": result["questions"]}


@router.post("/ai/qa")
def ai_qa(body: AIQARequest):
    """Answer from business rules only; this route has no database dependency."""
    return answer_question(body.question)


@router.post("/ai/explain-match")
def ai_explain_match(body: AIMatchExplanationRequest):
    """Explain existing match reasons without recalculating or writing state."""
    return explain_match(body.candidate.model_dump())
