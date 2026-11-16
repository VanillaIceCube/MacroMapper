"""Bounded preparation, trusted approval and durable execution outcomes."""

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
    status: Literal[
        "prepared",
        "approved",
        "cancelled",
        "expired",
        "completed",
        "in_progress",
        "uncertain",
    ]
    applied: bool | None
    replayed: bool = False
    result: Result
