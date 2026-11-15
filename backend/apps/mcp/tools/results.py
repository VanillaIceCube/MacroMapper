"""Bounded JSON representations and truthful mutation receipts."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import ValidationError


def json_value(value, *, maximum=32768, max_nodes=2000, max_collection=100):
    """Reject nonfinite/unbounded nested input before serializer or provider work."""
    nodes = 0

    def walk(item, depth=0):
        nonlocal nodes
        nodes += 1
        if (
            nodes > max_nodes
            or depth > 12
            or (isinstance(item, (list, dict)) and len(item) > max_collection)
        ):
            raise ValidationError("Request is too complex; use smaller operations.")
        if isinstance(item, dict):
            for child in item.values():
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)

    walk(value)
    encoded = json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False)
    if len(encoded.encode()) > maximum:
        raise ValidationError("Request is too large; use a narrower result.")
    return json.loads(encoded)


def result(value, **extra):
    truncated = False

    def trim(item, depth=0):
        nonlocal truncated
        if depth > 10:
            truncated = True
            return None
        if isinstance(item, str) and len(item) > 2000:
            truncated = True
            return item[:2000]
        if isinstance(item, (list, tuple)):
            truncated |= len(item) > 20
            return [trim(child, depth + 1) for child in item[:20]]
        if isinstance(item, dict):
            return {key: trim(child, depth + 1) for key, child in item.items()}
        return item

    return {
        "data": json_value(trim(value), maximum=65536),
        "truncated": truncated,
        **extra,
    }


def paid_receipt(action, proposal, *, retained=True, meal_id=None, applied=True):
    """Fixed-size receipt survives an oversized paid result, including temporary builders."""
    return {
        "action": action,
        "proposal_id": proposal.pk if retained else None,
        "temporary_proposal_id": None if retained else proposal.pk,
        "proposal_retained": retained,
        "source_meal_id": meal_id,
        "effect": "proposal_review" if retained else "temporary_adjustment_only",
        "diary_mutated": False,
        "applied": applied,
        "name": proposal.name[:120],
        "entry_date": proposal.entry_date.isoformat(),
        "item_count": len(proposal.items),
        "items": [
            {
                "key": str(item.get("key", ""))[:160],
                "name": str(item.get("name", ""))[:200],
                "servings": str(item.get("servings", ""))[:64],
            }
            for item in proposal.items[:20]
        ],
        "detail": "Result truncated. Retained proposals can be inspected in MacroMapper; temporary adjustments have only this bounded summary. Do not repeat a paid call automatically.",
    }


def paid_result(output, receipt):
    try:
        return result(output)
    except (ValidationError, ValueError, TypeError, OverflowError):
        # All fields in the receipt are fixed, bounded primitives. Never turn a
        # committed paid change into an error merely because its output is large.
        return {"data": receipt, "truncated": True}
