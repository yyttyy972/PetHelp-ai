"""Authenticated, read-only AI parsing endpoint for the week-10 backend."""
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from app.routers.api import Error, db, me
from .contract import normalize_ai_result
from .parser import AIConfigurationError, AIModelResponseError, parse_request
from .schema import AIResponseValidationError

router = APIRouter(prefix="/api/v0")

class AIParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=5000)
    reference_time: AwareDatetime
    timezone: str = Field(min_length=1, max_length=80)
    pet_ids: list[UUID] = Field(min_length=1, max_length=20)
    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc: raise ValueError("timezone must be a valid IANA timezone") from exc
        return value
    @model_validator(mode="after")
    def unique_pets(self):
        if len(set(self.pet_ids)) != len(self.pet_ids): raise ValueError("pet_ids must not contain duplicates")
        return self

@router.post("/ai/parse")
def ai_parse(body: AIParseRequest, user=Depends(me), c=Depends(db)):
    if "owner" not in user["roles"]: raise Error(403, "forbidden")
    rows = c.execute(
        'SELECT id, name, species, breed, birth_date, temperament, precautions, supplies_location, care_instructions FROM "PetProfile" WHERE owner_id=%s AND id = ANY(%s) AND deleted_at IS NULL',
        (user["id"], body.pet_ids),
    ).fetchall()
    by_id = {str(row["id"]): row for row in rows}
    selected_ids = [str(x) for x in body.pet_ids]
    if len(by_id) != len(selected_ids): raise Error(403, "forbidden", "所选宠物不存在或不属于当前用户")
    pets = []
    for pet_id in selected_ids:
        row = by_id[pet_id]
        pets.append({"id":pet_id,"name":row["name"],"species":row["species"],"breed":row["breed"],"birth_date":row["birth_date"].isoformat() if row["birth_date"] else None,"temperament":row["temperament"],"precautions":row["precautions"],"supplies_location":row["supplies_location"],"care_instructions":row["care_instructions"]})
    try:
        result = parse_request(body.text, body.reference_time.isoformat(), body.timezone, pets)
        return normalize_ai_result(result, selected_ids, body.text)
    except AIConfigurationError: raise Error(503, "ai_unavailable")
    except (AIModelResponseError, AIResponseValidationError, ValueError) as exc:
        logging.warning("AI parse response rejected: %s", exc)
        raise Error(502, "ai_parse_failed")
    except Exception:
        logging.exception("AI parse request failed")
        raise Error(503, "ai_unavailable")
