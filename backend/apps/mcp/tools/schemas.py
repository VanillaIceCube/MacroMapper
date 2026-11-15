"""Bounded results and automatic execution status; no human approval state."""

from typing import Literal

from pydantic import BaseModel, JsonValue


class Result(BaseModel):
    data: JsonValue
    truncated: bool = False
    has_more: bool = False
    next_offset: int | None = None


class ExecutionResult(BaseModel):
    request_id: str
    action: str
    status: Literal["completed", "in_progress", "uncertain"]
    applied: bool | None
    replayed: bool = False
    result: Result
