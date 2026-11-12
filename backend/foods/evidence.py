"""Additive evidence metadata; legacy provenance remains readable and immutable."""

import re
from decimal import Decimal, InvalidOperation

from .nutrients import NUTRIENT_FIELDS


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def usable_nutrition(nutrients):
    """Zero is meaningful; one finite nonnegative nutrient is sufficient."""
    for field in NUTRIENT_FIELDS:
        try:
            value = Decimal(str(nutrients.get(field)))
            if value.is_finite() and value >= 0:
                return True
        except (InvalidOperation, ValueError, TypeError):
            # Unknown or malformed fields cannot establish usable nutrition;
            # another independently valid nutrient may still make this partial food usable.
            continue
    return False


def source_matches(item, source):
    evidence = source.get("evidence") or {}
    return bool(
        evidence.get("retrieved") is True
        and normalized(evidence.get("product_name")) == normalized(item.get("name"))
        and normalized(evidence.get("brand")) == normalized(item.get("provider_name"))
        and evidence.get("region")
        and normalized(evidence["region"]) == normalized(item.get("region"))
        and evidence.get("serving_quantity") is not None
        and Decimal(str(evidence["serving_quantity"]))
        == Decimal(str(item.get("serving_quantity", 1)))
        and evidence.get("serving_unit") == item.get("serving_unit")
        and normalized(evidence.get("serving_label"))
        == normalized(item.get("serving_label"))
        and evidence.get("serving_weight_grams") is not None
        and item.get("serving_weight_grams") is not None
        and Decimal(str(evidence["serving_weight_grams"]))
        == Decimal(str(item["serving_weight_grams"]))
    )


def nutrition_evidence(item, *, research_status="not_attempted"):
    """Verification concerns exact displayed fields, never confidence or ancestry."""
    coverage = {}
    for field, value in item.get("nutrients", {}).items():
        if field not in NUTRIENT_FIELDS or value is None:
            continue
        urls = []
        for source in item.get("sources", []):
            if source.get("is_official") is not True or not source_matches(
                item, source
            ):
                continue
            source_value = source["evidence"].get("nutrients", {}).get(field)
            if source_value is not None and Decimal(str(value)) == Decimal(
                str(source_value)
            ):
                urls.append(source["url"])
        coverage[field] = {
            "status": "official_verified" if urls else "ai_estimate",
            "source_urls": urls,
        }
    verified = sum(
        field["status"] == "official_verified" for field in coverage.values()
    )
    children = item.get("components", [])
    all_verified = bool(coverage) and verified == len(coverage)
    inferred_components = any(
        child.get("evidence", {}).get("status") != "official_verified"
        for child in children
    )
    status = "ai_estimate"
    if all_verified:
        status = (
            "source_backed_ai_components"
            if inferred_components
            else "official_verified"
        )
    elif verified:
        status = "partially_source_backed"
    model_confidence = item.get("confidence_score")
    dependencies = [model_confidence] + [
        child.get("evidence", {})
        .get("confidence", {})
        .get("combined", child.get("confidence_score"))
        for child in children
    ]
    combined = (
        min(float(value) for value in dependencies)
        if all(value is not None for value in dependencies)
        else None
    )
    return {
        "status": status,
        "research_status": research_status,
        "region": item.get("region", ""),
        "nutrients": coverage,
        "confidence": {
            "model": float(model_confidence) if model_confidence is not None else None,
            "evidence": None,
            "combined": combined,
        },
    }


def version_evidence(version):
    if version.evidence:
        return version.evidence
    return {
        "status": "legacy_unverified",
        "research_status": "not_recorded",
        "nutrients": {},
    }


def source_data(source):
    return {
        "title": source.title,
        "provider": source.provider,
        "url": source.url,
        "accessed_on": source.accessed_on.isoformat() if source.accessed_on else None,
        # Null means unknown legacy source-level classification, not inherited official status.
        "is_official": source.is_official is True,
        "evidence": source.evidence,
    }
