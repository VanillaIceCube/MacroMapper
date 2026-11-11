"""Bounded structured results, with private token/confirmation state excluded."""

from pydantic import BaseModel, JsonValue


class Result(BaseModel):
    data: JsonValue
    truncated: bool = False
    has_more: bool = False
    next_offset: int | None = None


class PreviewResult(BaseModel):
    confirmation_id: str
    expires_at: str
    action: str
    target_id: int | None
    changes: dict[str, JsonValue]
    current: JsonValue
    paid: bool
    instruction: str


class ConfirmResult(BaseModel):
    applied: bool
    action: str
    result: Result
