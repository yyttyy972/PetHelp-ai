from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
class Register(Model):
    account: str = Field(min_length=1,max_length=100)
    password: str = Field(min_length=8,max_length=128)
    display_name: str = Field(min_length=1,max_length=60)
    roles: list[Literal["owner","helper"]] = Field(min_length=1)
    avatar_url: str|None = Field(None,max_length=255)
    address: str|None = None
class Login(Model):
    account: str
    password: str
class UserPatch(Model):
    display_name: str|None = Field(None,min_length=1,max_length=60)
    roles: list[Literal["owner","helper"]]|None = Field(None,min_length=1)
    avatar_url: str|None = Field(None,max_length=255)
    address: str|None = None
class Pet(Model):
    name: str = Field(min_length=1,max_length=60)
    species: Literal["cat","dog"]
    breed: str|None = Field(None,max_length=60)
    birth_date: date
    temperament: str|None = None
    precautions: str|None = None
    supplies_location: str|None = None
    care_instructions: str|None = None
    photo_url: str|None = Field(None,max_length=255)
    @model_validator(mode="after")
    def birth(self):
        if self.birth_date > date.today(): raise ValueError("birth_date is in the future")
        return self
class Helper(Model):
    service_types: list[Literal["home_visit","dog_walking","errand_buy"]] = Field(min_length=1)
    service_area: str = Field(min_length=1)
    experience: str = Field(min_length=1)
    supported_species: list[Literal["cat","dog"]] = Field(min_length=1)
    service_radius_m: int = Field(gt=0)
    fee_pref: Literal["free","paid","both"]|None = None
    verification_status: Literal["unverified","verified"]|None = None
    address_tag: str|None = Field(None,max_length=50)
class Window(Model):
    start_at: AwareDatetime
    end_at: AwareDatetime
    @model_validator(mode="after")
    def window(self):
        if self.end_at<=self.start_at: raise ValueError("end must follow start")
        return self
class Item(Model):
    item_key: str = Field(min_length=1,max_length=60)
    pet_id: UUID|None = None
    position: int = Field(gt=0)
    content: str = Field(min_length=1)
    completion_condition: str = Field(min_length=1)
    required: bool = True
    product_name: str|None = Field(None,max_length=160)
    quantity: int|None = Field(None,gt=0)
    unit: str|None = Field(None,max_length=20)
class Demand(Model):
    pet_ids: list[UUID] = Field(min_length=1)
    service_type: Literal["home_visit","dog_walking","errand_buy"]
    fee_type: Literal["free","paid"]
    window_start: AwareDatetime
    window_end: AwareDatetime
    expected_duration_minutes: int = Field(gt=0)
    location: str = Field(min_length=1)
    budget: Decimal = Field(ge=0,max_digits=10,decimal_places=2)
    handover_notes: str = Field(min_length=1)
    emergency_contact: str = Field(min_length=1)
    requirements: str|None = None
    precautions: str|None = None
    raw_text: str|None = None
    checklist_items: list[Item] = Field(min_length=1)
    @model_validator(mode="after")
    def check(self):
        if (self.window_end-self.window_start).total_seconds()<self.expected_duration_minutes*60: raise ValueError("invalid window")
        if len(set(self.pet_ids))!=len(self.pet_ids): raise ValueError("duplicate pets")
        for field in ("item_key","position"):
            if len({getattr(i,field) for i in self.checklist_items})!=len(self.checklist_items): raise ValueError("duplicate checklist key/position")
        for item in self.checklist_items:
            if item.pet_id and item.pet_id not in self.pet_ids: raise ValueError("item pet outside request")
            product=[item.product_name,item.quantity,item.unit]
            if any(x is not None for x in product) and (not all(x is not None for x in product) or self.service_type!="errand_buy"): raise ValueError("invalid product fields")
        keys={i.item_key for i in self.checklist_items}
        required={"dog_walking":{"pickup","departure","return"},"errand_buy":{"purchase","delivery"}}.get(self.service_type,set())
        if not required<=keys: raise ValueError("required service steps missing")
        return self
class Publish(Model):
    expected_version: int = Field(gt=0)
