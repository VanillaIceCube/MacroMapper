"""Conservative food identity and immutable definition/evidence fingerprints."""

import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .nutrients import NUTRIENT_FIELDS


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def identity_text(value):
    value = unicodedata.normalize("NFKD", str(value)).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, re.UNICODE))


def provider_identity(value):
    return identity_text(value).replace(" ", "")


def product_name(value, provider=""):
    words = identity_text(value).split()
    # Conservative known food plurals; do not stem arbitrary product/SKU words.
    plurals = {
        "apples": "apple",
        "eggs": "egg",
        "browns": "brown",
        "tomatoes": "tomato",
        "carrots": "carrot",
        "bananas": "banana",
        "breasts": "breast",
    }
    normalized = " ".join(plurals.get(word, word) for word in words)
    provider_key = provider_identity(provider)
    normalized_words = normalized.split()
    for end in range(1, len(normalized_words)):
        if provider_key and "".join(normalized_words[:end]) == provider_key:
            normalized = " ".join(normalized_words[end:])
            break
    return normalized


def canonical_url(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    query = urlencode(
        sorted(
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in {"fbclid", "gclid"}
        )
    )
    return urlunsplit(("https", host, parsed.path.rstrip("/") or "/", query, ""))


def identity_source_url(*, provider_name, sources):
    """Use provider-name hostname hints; this is not an ownership verifier."""
    provider = provider_identity(provider_name)
    if not provider:
        return ""
    urls = []
    for source in sources:
        url = source.get("url", "")
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        if host.split(".")[0] == provider:
            urls.append(canonical_url(url))
    return min(urls, default="")


def canonical_food_identity(
    *,
    name,
    provider_name="",
    origin_type="generic",
    market="",
    product_identifier="",
    identity_url="",
    sources=(),
):
    if origin_type == "generic" and not provider_name:
        from .portions import canonical_generic_name

        name = canonical_generic_name(name)
    url = identity_url or identity_source_url(
        provider_name=provider_name, sources=sources
    )
    return digest(
        {
            "name": product_name(name, provider_name),
            "provider": provider_identity(provider_name),
            # Restaurant/branded classification is presentation metadata for a named provider.
            "kind": "provider" if provider_name else origin_type,
            "market": identity_text(market),
            "product_identifier": str(product_identifier).strip().casefold(),
            "url": canonical_url(url) if url and not product_identifier else "",
        }
    )


def validate_natural_servings(value):
    from .portions import clean_natural_servings

    clean_natural_servings(value)


def number(value, places=4):
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-places)))


def definition_fingerprint(definition):
    components = []
    for component in definition.get("components", []):
        version = (
            component.get("food_version") or component["food_item"].current_version
        )
        child = version.food_item
        components.append(
            {
                "food": child.canonical_identity
                or canonical_food_identity(
                    name=child.name,
                    provider_name=child.provider_name,
                    origin_type=child.origin_type,
                    market=child.market,
                    product_identifier=child.product_identifier,
                    identity_url=child.identity_url,
                    sources=[{"url": source.url} for source in version.sources.all()],
                ),
                "version": version.content_fingerprint or version_fingerprint(version),
                "servings": number(component["servings"]),
                "order": component.get("order", 0),
            }
        )
    return digest(
        {
            **{
                key: number(definition.get(key), 3)
                for key in (
                    "serving_quantity",
                    "serving_weight_grams",
                    "serving_volume_ml",
                )
            },
            "serving_unit": definition["serving_unit"],
            "serving_label": identity_text(definition.get("serving_label", "")),
            "natural_servings": sorted(
                (
                    {
                        "key": option["key"],
                        "label": identity_text(option["label"]),
                        "weight_grams": number(option["weight_grams"], 3),
                    }
                    for option in definition.get("natural_servings", [])
                ),
                key=lambda option: option["key"],
            ),
            "nutrients": {
                key: number(definition.get("nutrients", {}).get(key))
                for key in NUTRIENT_FIELDS
            },
            "components": components,
            # Trust and research coverage are immutable definition semantics. Model
            # confidence and per-request retrieval IDs remain append-only metadata.
            "evidence": {
                key: value
                for key, value in definition.get("evidence", {}).items()
                if key != "confidence"
            },
            "source_evidence": sorted(
                (
                    {
                        "url": source["url"],
                        "is_official": source.get("is_official"),
                        "evidence": {
                            key: value
                            for key, value in source.get("evidence", {}).items()
                            if key != "retrieval_response_id"
                        },
                    }
                    for source in definition.get("sources", [])
                    if source.get("is_official") is True or source.get("evidence")
                ),
                key=lambda source: source["url"],
            ),
        }
    )


def version_definition(version):
    return {
        **{
            key: getattr(version, key)
            for key in (
                "serving_quantity",
                "serving_unit",
                "serving_label",
                "serving_weight_grams",
                "serving_volume_ml",
                "natural_servings",
                "provenance",
                "evidence",
                "confidence_score",
                "estimation_provider",
                "estimation_model",
                "estimation_response_id",
                "derived_from",
            )
        },
        "nutrients": {key: getattr(version, key) for key in NUTRIENT_FIELDS},
        "sources": [
            {
                key: getattr(source, key)
                for key in (
                    "title",
                    "provider",
                    "url",
                    "accessed_on",
                    "is_official",
                    "evidence",
                )
            }
            for source in version.sources.all()
        ],
        "components": [
            {
                "food_item": component.child_version.food_item,
                "food_version": component.child_version,
                "servings": component.servings,
                "order": component.order,
            }
            for component in version.components.select_related(
                "child_version__food_item"
            )
        ],
    }


def version_fingerprint(version):
    return definition_fingerprint(version_definition(version))


def evidence_metadata(definition):
    metadata = {
        key: str(definition.get(key) or "")
        for key in (
            "provenance",
            "confidence_score",
            "estimation_provider",
            "estimation_model",
            "estimation_response_id",
        )
    }
    if metadata["confidence_score"]:
        metadata["confidence_score"] = number(metadata["confidence_score"], 3)
    if definition.get("evidence"):
        metadata["nutrition_evidence"] = definition["evidence"]
    if any(
        source.get("evidence") or source.get("is_official") is not None
        for source in definition.get("sources", [])
    ):
        metadata["sources"] = [
            {
                key: value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in source.items()
            }
            for source in definition.get("sources", [])
        ]
    return metadata
