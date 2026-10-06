from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


def uid(prefix: str) -> str:
    return prefix + "_" + uuid4().hex[:16]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_model: str = Field(min_length=3, max_length=120)
    installed_modules_gb: list[int] | None = None
    free_slots: int | None = Field(default=None, ge=0, le=8)
    upgrade_action: Literal["add_module", "replace_all"] = "add_module"
    desired_capacity_gb: int = Field(default=16, ge=1, le=256)
    country: str = Field(default="IN", pattern=r"^[A-Za-z]{2}$")
    part_number: str | None = Field(default=None, max_length=100)
    mode: Literal["live", "replay"] = "live"

    @field_validator("device_model", "part_number")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter a non-empty value.")
        return value

    @field_validator("installed_modules_gb")
    @classmethod
    def modules(cls, value):
        if value is not None and (
            len(value) > 8 or any(type(x) is not int or not 1 <= x <= 256 for x in value)
        ):
            raise ValueError("Enter up to eight positive module capacities.")
        return value


class Source(BaseModel):
    id: str = Field(default_factory=lambda: uid("src"))
    url: str
    title: str
    publisher: str
    source_type: Literal["manufacturer", "retailer", "marketplace", "search_result", "other"]
    retrieved_at: str = Field(default_factory=utcnow)
    text: str = ""
    content_hash: str = ""
    origin: Literal["live", "cache", "replay"] = "live"
    fetch_status: Literal["available", "unavailable"] = "available"
    search_id: str | None = None


FactField = Literal[
    "identity",
    "memory_generation",
    "memory_form_factor",
    "maximum_capacity_gb",
    "memory_slots",
    "module_capacity_gb",
    "module_maximum_gb",
    "memory_speed_mts",
    "memory_ecc",
    "memory_voltage_v",
    "memory_buffering",
    "memory_replaceable",
    "manufacturer_listed",
    "documented_restrictions",
]


class FactDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    field: FactField
    value: str | int | float | bool
    evidence_span: str = Field(min_length=3, max_length=1800)
    related_subject: str | None = None


class Extraction(BaseModel):
    facts: list[FactDraft] = Field(default_factory=list, max_length=40)


class Fact(FactDraft):
    id: str = Field(default_factory=lambda: uid("fact"))
    source_id: str
    status: Literal["supported", "unverified"] = "unverified"
    confidence: Literal["high", "unverified"] = "unverified"
    validation_reason: str = ""


class Offer(BaseModel):
    id: str = Field(default_factory=lambda: uid("offer"))
    title: str
    part_number: str | None = None
    manufacturer: str | None = None
    price: str | None = None
    currency: str | None = None
    seller: str | None = None
    url: str | None = None
    observed_at: str = Field(default_factory=utcnow)
    identity_status: Literal["unresolved", "resolved"] = "unresolved"
    origin: Literal["live", "cache", "user", "replay"] = "live"
    result: str = "NEEDS_INFORMATION"
    manufacturer_listed: bool = False


class Check(BaseModel):
    id: str = Field(default_factory=lambda: uid("check"))
    offer_id: str
    check_type: str
    label: str
    status: Literal["pass", "conflict", "unknown"]
    critical: bool = True
    explanation: str
    required: Any = None
    observed: Any = None
    source_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)


class Clarification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_model: str | None = Field(default=None, min_length=3, max_length=120)
    installed_modules_gb: list[int] | None = None
    free_slots: int | None = Field(default=None, ge=0, le=8)
    upgrade_action: Literal["add_module", "replace_all"] | None = None


class AddOffer(BaseModel):
    part_number: str = Field(min_length=3, max_length=100)
