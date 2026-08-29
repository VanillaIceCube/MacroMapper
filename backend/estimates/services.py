from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS
from foods.portions import portion_options_for_serving
from foods.services import create_food_item
from meals.models import MealEntry
from meals.services import _effective_nutrients, replace_meal_items

from .models import MealProposal, MealProposalRevision
from .provider import EstimationProviderError, get_estimation_provider

STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "from",
    "in",
    "of",
    "the",
    "to",
    "with",
}

QUERY_IGNORED_WORDS = STOP_WORDS | {
    "ate",
    "eat",
    "eating",
    "got",
    "had",
    "meal",
    "oar",
    "or",
    "order",
    "ordered",
    "please",
    "plus",
}

QUANTITY_WORDS = {
    "single": Decimal("1"),
    "one": Decimal("1"),
    "two": Decimal("2"),
    "three": Decimal("3"),
    "four": Decimal("4"),
    "five": Decimal("5"),
    "six": Decimal("6"),
    "seven": Decimal("7"),
    "eight": Decimal("8"),
    "nine": Decimal("9"),
    "ten": Decimal("10"),
    "eleven": Decimal("11"),
    "twelve": Decimal("12"),
}

QUERY_TOKEN_PATTERN = re.compile(
    r"\d+(?:\.\d+)?x?|[^\W\d_]+(?:['’][^\W\d_]+)*",
    re.UNICODE,
)

QUANTITY_BOUNDARY_PATTERN = "|".join(
    [r"\d+(?:\.\d+)?x?", *sorted(QUANTITY_WORDS, key=len, reverse=True)]
)

FOOD_CLAUSE_SEPARATOR_PATTERN = re.compile(
    rf"\s*(?:\+|;|\r?\n|,\s*(?:and|plus)\b|"
    rf"\b(?:and|plus)\b(?=\s+(?:{QUANTITY_BOUNDARY_PATTERN})\b))\s*",
    re.IGNORECASE,
)

FOOD_ITEM_BOUNDARY_PATTERN = re.compile(
    r"(?:\+|;|,|\b(?:and|plus)\b)",
    re.IGNORECASE,
)

UNSAFE_CATALOG_TEXT_PATTERN = re.compile(
    r"(?:[\x00-\x1f\x7f]|<[^>]*>|https?://|www\.|\b(?:ignore|override)\b.{0,40}"
    r"\b(?:instruction|prompt|system|developer)\b|\b(?:system|developer|assistant|user)"
    r"\s*:|\b(?:private|personal)\s+(?:meal|note|data|information)\b)",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")


def _normalize_search_token(value):
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _quantity(value):
    normalized = _normalize_search_token(value)
    if normalized in QUANTITY_WORDS:
        return QUANTITY_WORDS[normalized]
    numeric_match = re.fullmatch(r"(\d+(?:\.\d+)?)(?:x)?", value.casefold())
    if numeric_match is None:
        return None
    quantity = Decimal(numeric_match.group(1))
    return quantity if quantity > 0 else None


def _query_tokens(value):
    return [
        {
            "index": index,
            "raw": match.group(0),
            "normalized": _normalize_search_token(match.group(0)),
            "quantity": _quantity(match.group(0)),
            "char_start": match.start(),
            "char_end": match.end(),
        }
        for index, match in enumerate(QUERY_TOKEN_PATTERN.finditer(value))
    ]


def _identity_tokens(value):
    return [
        token["normalized"]
        for token in _query_tokens(value)
        if token["normalized"] not in QUERY_IGNORED_WORDS and token["quantity"] is None
    ]


def _best_phrase_span(*, phrase_tokens, query_tokens):
    if not phrase_tokens or not query_tokens:
        return None
    target = "".join(phrase_tokens)
    best = None
    maximum_window = min(len(query_tokens), len(phrase_tokens) + 1)
    for window_size in range(1, maximum_window + 1):
        for start in range(len(query_tokens) - window_size + 1):
            window = query_tokens[start : start + window_size]
            candidate = "".join(token["normalized"] for token in window)
            score = SequenceMatcher(None, target, candidate).ratio()
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "indexes": {token["index"] for token in window},
                    "start": window[0]["index"],
                    "end": window[-1]["index"],
                }
    return best


def _catalog_food_rank(food, *, user):
    provenance_rank = {
        FoodItemVersion.Provenance.OFFICIAL: 5,
        FoodItemVersion.Provenance.USER_ENTERED: 4,
        FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE: 3,
        FoodItemVersion.Provenance.COMMUNITY_ESTIMATE: 2,
        FoodItemVersion.Provenance.AI_ESTIMATE: 1,
    }
    version = food.current_version
    return (
        int(food.owner_id == user.pk),
        provenance_rank.get(version.provenance, 0),
        len(version.sources.all()),
        version.confidence_score or Decimal("-1"),
        food.pk,
    )


def _description_clauses(description):
    clauses = [
        clause.strip()
        for clause in FOOD_CLAUSE_SEPARATOR_PATTERN.split(description)
        if clause.strip()
    ]
    return clauses or [description.strip()]


def _shared_provider_context(*, description, foods, user):
    query_tokens = [
        token
        for token in _query_tokens(description)
        if token["quantity"] is None and token["normalized"] not in QUERY_IGNORED_WORDS
    ]
    providers = {}
    for food in foods:
        provider_tokens = _identity_tokens(food.provider_name)
        if not provider_tokens:
            continue
        match = _best_phrase_span(
            phrase_tokens=provider_tokens,
            query_tokens=query_tokens,
        )
        if match is None or match["score"] < 0.78:
            continue
        identity = "".join(provider_tokens)
        candidate = (
            match["score"],
            len(provider_tokens),
            len(identity),
            _catalog_food_rank(food, user=user),
            food.provider_name,
        )
        if identity not in providers or candidate > providers[identity]:
            providers[identity] = candidate
    if len(providers) != 1:
        return ""
    return next(iter(providers.values()))[-1]


def _append_provider_context(description, provider_name):
    if not description or not provider_name:
        return description
    provider_match = _best_phrase_span(
        phrase_tokens=_identity_tokens(provider_name),
        query_tokens=[
            token
            for token in _query_tokens(description)
            if token["quantity"] is None
            and token["normalized"] not in QUERY_IGNORED_WORDS
        ],
    )
    if provider_match is not None and provider_match["score"] >= 0.78:
        return description
    return f"{description} {provider_name}"


def _has_partial_catalog_conflict(*, description, matches, unmatched_tokens):
    if not matches or not unmatched_tokens:
        return False
    tokens_by_index = {token["index"]: token for token in _query_tokens(description)}
    for match in matches:
        start_token = tokens_by_index[match["start"]]
        end_token = tokens_by_index[match["end"]]
        before = [
            token for token in unmatched_tokens if token["index"] < start_token["index"]
        ]
        after = [
            token for token in unmatched_tokens if token["index"] > end_token["index"]
        ]
        neighboring_tokens = []
        if before:
            neighboring_tokens.append(max(before, key=lambda token: token["index"]))
        if after:
            neighboring_tokens.append(min(after, key=lambda token: token["index"]))
        for token in neighboring_tokens:
            if token["index"] < start_token["index"]:
                gap = description[token["char_end"] : start_token["char_start"]]
            else:
                gap = description[end_token["char_end"] : token["char_start"]]
            if not FOOD_ITEM_BOUNDARY_PATTERN.search(gap):
                return True
    return False


def _quantity_for_match(*, match, all_tokens, used_quantity_indexes):
    for index in range(match["start"] - 1, max(match["start"] - 4, -1), -1):
        token = all_tokens[index]
        if token["index"] in used_quantity_indexes:
            continue
        if token["quantity"] is not None:
            used_quantity_indexes.add(token["index"])
            return token["quantity"]
        if (
            token["index"] in match["provider_indexes"]
            or token["normalized"] in QUERY_IGNORED_WORDS
        ):
            continue
        break
    next_index = match["end"] + 1
    if next_index < len(all_tokens):
        token = all_tokens[next_index]
        if (
            token["quantity"] is not None
            and token["index"] not in used_quantity_indexes
        ):
            used_quantity_indexes.add(token["index"])
            return token["quantity"]
    return Decimal("1")


def _decimal(value, *, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _storage_decimal(value, *, decimal_places, default="0"):
    quantum = Decimal("1").scaleb(-decimal_places)
    return _decimal(value, default=default).quantize(quantum, rounding=ROUND_HALF_UP)


def _decimal_string(value):
    return format(Decimal(value).normalize(), "f")


def _source_kind(provenance):
    if provenance == FoodItemVersion.Provenance.OFFICIAL:
        return "official_verified"
    if provenance == FoodItemVersion.Provenance.AI_ESTIMATE:
        return "ai_estimate"
    if provenance == FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE:
        return "user_modified_estimate"
    return "catalog_estimate"


def _sources(version):
    return [
        {
            "title": source.title,
            "provider": source.provider,
            "url": source.url,
            "accessed_on": (
                source.accessed_on.isoformat() if source.accessed_on else None
            ),
            "is_official": version.provenance == FoodItemVersion.Provenance.OFFICIAL,
        }
        for source in version.sources.all()
    ]


def _portion_options(item):
    return item.get("portion_options") or portion_options_for_serving(
        quantity=item.get("serving_quantity", "1"),
        unit=item.get("serving_unit", FoodItemVersion.ServingUnit.SERVING),
        label=item.get("serving_label", ""),
        weight_grams=item.get("serving_weight_grams"),
        volume_milliliters=item.get("serving_volume_ml"),
    )


def _catalog_food(version, *, servings="1", key=None, depth=0):
    food = version.food_item
    item_key = key or f"catalog-{food.pk}"
    nutrients = _effective_nutrients(version)
    portion_options = portion_options_for_serving(
        quantity=version.serving_quantity,
        unit=version.serving_unit,
        label=version.serving_label,
        weight_grams=version.serving_weight_grams,
        volume_milliliters=version.serving_volume_ml,
    )
    option_keys = {option["key"] for option in portion_options}
    if depth and "fl_oz" in option_keys:
        selected_portion_key = "fl_oz"
    elif depth and "g" in option_keys:
        selected_portion_key = "g"
    else:
        selected_portion_key = (
            version.serving_unit if version.serving_unit in option_keys else "base"
        )
    return {
        "key": item_key,
        "food_item_id": food.pk,
        "food_version_id": version.pk,
        "name": food.name,
        "provider_name": food.provider_name,
        "origin_type": food.origin_type,
        "servings": str(servings),
        "serving_quantity": str(version.serving_quantity),
        "serving_unit": version.serving_unit,
        "serving_label": version.serving_label,
        "serving_weight_grams": (
            str(version.serving_weight_grams)
            if version.serving_weight_grams is not None
            else None
        ),
        "serving_volume_ml": (
            str(version.serving_volume_ml)
            if version.serving_volume_ml is not None
            else None
        ),
        "portion_options": portion_options,
        "selected_portion_key": selected_portion_key,
        "provenance": version.provenance,
        "source_kind": _source_kind(version.provenance),
        "confidence_score": (
            str(version.confidence_score)
            if version.confidence_score is not None
            else None
        ),
        "is_user_modified": (
            version.provenance == FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE
        ),
        "nutrients": {
            field: _decimal_string(amount) if amount is not None else None
            for field, amount in nutrients.items()
        },
        "sources": _sources(version),
        "components": [
            _catalog_food(
                component.child_version,
                servings=component.servings,
                key=f"{item_key}.{index}",
                depth=depth + 1,
            )
            for index, component in enumerate(version.components.all())
        ],
    }


def _visible_catalog_foods(user):
    return list(
        FoodItem.objects.active()
        .visible_to(user)
        .filter(current_version__isnull=False)
        .select_related("current_version")
        .prefetch_related(
            "current_version__sources",
            "current_version__components__child_version__food_item",
            "current_version__components__child_version__sources",
            "current_version__components__child_version__components",
        )
    )


def _token_similarity(left, right):
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _tokens_are_covered(required_tokens, candidate_tokens, *, threshold=0.86):
    return bool(required_tokens) and all(
        any(
            _token_similarity(required, candidate) >= threshold
            for candidate in candidate_tokens
        )
        for required in required_tokens
    )


def _intent_search_tokens(intent):
    provider_tokens = set(_identity_tokens(intent.get("provider_name", "")))
    return [
        token
        for token in _identity_tokens(intent.get("search_name", ""))
        if token not in provider_tokens
    ]


def _intent_defining_tokens(intent):
    explicit = [
        token
        for term in intent.get("defining_terms", [])
        for token in _identity_tokens(term)
    ]
    return explicit or _intent_search_tokens(intent)


def _intent_queries(intent):
    values = [intent.get("search_name", ""), *intent.get("aliases", [])]
    provider_tokens = set(_identity_tokens(intent.get("provider_name", "")))
    queries = []
    seen = set()
    for value in values:
        tokens = [
            token for token in _identity_tokens(value) if token not in provider_tokens
        ]
        identity = "".join(tokens)
        if tokens and identity not in seen:
            seen.add(identity)
            queries.append(tokens)
    return queries


def _resolve_catalog_intent(*, intent, user, foods):
    provider_tokens = _identity_tokens(intent.get("provider_name", ""))
    provider_identity = "".join(provider_tokens)
    defining_tokens = _intent_defining_tokens(intent)
    queries = _intent_queries(intent)
    if not defining_tokens or not queries:
        return None

    candidates = []
    for food in foods:
        food_provider_tokens = _identity_tokens(food.provider_name)
        food_provider_identity = "".join(food_provider_tokens)
        if provider_identity:
            provider_score = _token_similarity(
                provider_identity,
                food_provider_identity,
            )
            if provider_score < 0.78:
                continue
        else:
            provider_score = 0
            if food.origin_type in {
                FoodItem.OriginType.BRANDED,
                FoodItem.OriginType.RESTAURANT,
            }:
                continue

        food_name_tokens = _identity_tokens(food.name)
        food_definition_tokens = [
            *food_name_tokens,
            *_identity_tokens(food.current_version.serving_label),
        ]
        if not _tokens_are_covered(defining_tokens, food_definition_tokens):
            continue
        if not provider_identity and not any(
            _tokens_are_covered(food_name_tokens, query_tokens)
            for query_tokens in queries
        ):
            continue

        query_scores = []
        for query_tokens in queries:
            coverage_score = sum(
                max(
                    (
                        _token_similarity(query_token, food_token)
                        for food_token in food_name_tokens
                    ),
                    default=0,
                )
                for query_token in query_tokens
            ) / len(query_tokens)
            sequence_score = _token_similarity(
                "".join(query_tokens),
                "".join(food_name_tokens),
            )
            query_scores.append(max(coverage_score, sequence_score))
        name_score = max(query_scores)
        if name_score < 0.78:
            continue

        shortest_query = min(len(query) for query in queries)
        extra_name_tokens = max(len(food_name_tokens) - shortest_query, 0)
        candidates.append(
            {
                "food": food,
                "score": name_score,
                "provider_score": provider_score,
                "extra_name_tokens": extra_name_tokens,
                "food_rank": _catalog_food_rank(food, user=user),
            }
        )

    if not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            candidate["provider_score"],
            candidate["score"],
            -candidate["extra_name_tokens"],
            candidate["food_rank"],
        ),
        reverse=True,
    )
    selected = candidates[0]
    selected["servings"] = _decimal(intent.get("quantity"), default="1")
    return selected


def _validated_search_intents(result):
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        return []
    intents = []
    for item in result["items"][:20]:
        if not isinstance(item, dict):
            return []
        raw_text = str(item.get("raw_text", "")).strip()
        search_name = str(item.get("search_name", "")).strip()
        quantity = _decimal(item.get("quantity"), default="0")
        if not raw_text or not search_name or quantity <= 0:
            return []
        intents.append(
            {
                "raw_text": raw_text[:300],
                "search_name": search_name[:200],
                "provider_name": str(item.get("provider_name", "")).strip()[:160],
                "quantity": quantity,
                "defining_terms": [
                    str(term).strip()[:80]
                    for term in item.get("defining_terms", [])[:12]
                    if str(term).strip()
                ],
                "aliases": [
                    str(alias).strip()[:200]
                    for alias in item.get("aliases", [])[:10]
                    if str(alias).strip()
                ],
            }
        )
    return intents


def _brief_generated_meal_name(value):
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(name) <= 80:
        return name
    shortened = name[:80].rsplit(" ", 1)[0].rstrip(" ,&-/")
    return shortened or name[:80]


def resolve_catalog_intents(*, intents, user):
    foods = _visible_catalog_foods(user)
    matches = []
    matches_by_food_id = {}
    unmatched_descriptions = []
    for intent in intents:
        match = _resolve_catalog_intent(intent=intent, user=user, foods=foods)
        if match is None:
            unmatched_descriptions.append(intent["raw_text"])
            continue
        food_id = match["food"].pk
        if food_id in matches_by_food_id:
            matches_by_food_id[food_id]["servings"] += match["servings"]
            continue
        matches.append(match)
        matches_by_food_id[food_id] = match
    return {
        "matches": matches,
        "unmatched_description": " + ".join(unmatched_descriptions),
        "unmatched_descriptions": unmatched_descriptions,
    }


def _resolve_catalog_clause(*, description, user, foods):
    all_tokens = _query_tokens(description)
    query_tokens = [
        token
        for token in all_tokens
        if token["quantity"] is None and token["normalized"] not in QUERY_IGNORED_WORDS
    ]
    if not query_tokens:
        return {
            "matches": [],
            "unmatched_description": description,
            "unmatched_tokens": all_tokens,
        }

    best_identity_foods = {}
    for food in foods:
        identity = (
            "".join(_identity_tokens(food.provider_name)),
            "".join(_identity_tokens(food.name)),
        )
        existing = best_identity_foods.get(identity)
        if existing is None or _catalog_food_rank(food, user=user) > _catalog_food_rank(
            existing, user=user
        ):
            best_identity_foods[identity] = food

    candidates = []
    for food in best_identity_foods.values():
        name_tokens = _identity_tokens(food.name)
        name_match = _best_phrase_span(
            phrase_tokens=name_tokens,
            query_tokens=query_tokens,
        )
        minimum_score = 0.86 if len("".join(name_tokens)) <= 6 else 0.78
        if name_match is None or name_match["score"] < minimum_score:
            continue
        provider_match = _best_phrase_span(
            phrase_tokens=_identity_tokens(food.provider_name),
            query_tokens=query_tokens,
        )
        provider_indexes = (
            provider_match["indexes"]
            if provider_match is not None and provider_match["score"] >= 0.78
            else set()
        )
        candidates.append(
            {
                "food": food,
                "score": name_match["score"],
                "name_indexes": name_match["indexes"],
                "provider_indexes": provider_indexes,
                "provider_score": provider_match["score"] if provider_match else 0,
                "start": name_match["start"],
                "end": name_match["end"],
                "name_token_count": len(name_tokens),
                "name_character_count": len("".join(name_tokens)),
                "selection_score": name_match["score"]
                + min(len(name_tokens), 4) * 0.04,
                "food_rank": _catalog_food_rank(food, user=user),
            }
        )

    candidates.sort(
        key=lambda candidate: (
            candidate["selection_score"],
            candidate["name_token_count"],
            candidate["name_character_count"],
            candidate["score"],
            candidate["provider_score"],
            candidate["food_rank"],
        ),
        reverse=True,
    )
    selected = []
    claimed_name_indexes = set()
    for candidate in candidates:
        if candidate["name_indexes"] & claimed_name_indexes:
            continue
        selected.append(candidate)
        claimed_name_indexes.update(candidate["name_indexes"])
        if len(selected) == 20:
            break

    used_quantity_indexes = set()
    for match in selected:
        match["servings"] = _quantity_for_match(
            match=match,
            all_tokens=all_tokens,
            used_quantity_indexes=used_quantity_indexes,
        )
    selected.sort(key=lambda match: match["start"])

    covered_indexes = claimed_name_indexes | used_quantity_indexes
    for match in selected:
        covered_indexes.update(match["provider_indexes"])
    unmatched_tokens = [
        token
        for token in all_tokens
        if token["index"] not in covered_indexes
        and token["normalized"] not in QUERY_IGNORED_WORDS
    ]
    if _has_partial_catalog_conflict(
        description=description,
        matches=selected,
        unmatched_tokens=unmatched_tokens,
    ):
        return {
            "matches": [],
            "unmatched_description": description.strip(),
            "unmatched_tokens": all_tokens,
        }
    return {
        "matches": selected,
        "unmatched_description": " ".join(token["raw"] for token in unmatched_tokens),
        "unmatched_tokens": unmatched_tokens,
    }


def resolve_catalog_matches(*, description, user):
    foods = _visible_catalog_foods(user)
    provider_context = _shared_provider_context(
        description=description,
        foods=foods,
        user=user,
    )
    matches = []
    unmatched_descriptions = []
    for clause in _description_clauses(description):
        resolution = _resolve_catalog_clause(
            description=clause,
            user=user,
            foods=foods,
        )
        matches.extend(resolution["matches"])
        unmatched_description = resolution["unmatched_description"]
        if unmatched_description:
            unmatched_descriptions.append(
                _append_provider_context(unmatched_description, provider_context)
            )
    return {
        "matches": matches,
        "unmatched_description": " + ".join(unmatched_descriptions),
        "unmatched_descriptions": unmatched_descriptions,
    }


def find_catalog_matches(*, description, user):
    return [
        match["food"]
        for match in resolve_catalog_matches(
            description=description,
            user=user,
        )["matches"]
    ]


def _recalculate_item(item):
    item = dict(item)
    item["servings"] = str(_decimal(item.get("servings"), default="1"))
    item["portion_options"] = _portion_options(item)
    option_keys = {option["key"] for option in item["portion_options"]}
    if item.get("selected_portion_key") not in option_keys:
        item["selected_portion_key"] = item["portion_options"][0]["key"]
    components = [
        _recalculate_item(component) for component in item.get("components", [])
    ]
    item["components"] = components
    if components:
        nutrients = {}
        for field in NUTRIENT_FIELDS:
            known_components = [
                component
                for component in components
                if component.get("nutrients", {}).get(field) is not None
            ]
            if not known_components:
                nutrients[field] = None
            else:
                nutrients[field] = _decimal_string(
                    sum(
                        (
                            _decimal(component["nutrients"][field])
                            * _decimal(component["servings"], default="1")
                            for component in known_components
                        ),
                        Decimal("0"),
                    )
                )
        item["nutrients"] = nutrients
    return item


def normalize_items(items):
    return [_recalculate_item(item) for item in items]


def _items_by_key(items):
    indexed = {}
    for item in items:
        indexed[item["key"]] = item
        indexed.update(_items_by_key(item.get("components", [])))
    return indexed


@transaction.atomic
def create_proposal_revision(*, proposal, kind, created_by, follow_up="", message=""):
    locked_proposal = MealProposal.objects.select_for_update().get(pk=proposal.pk)
    parent = locked_proposal.revisions.order_by("-revision_number", "-id").first()
    revision = MealProposalRevision(
        proposal=locked_proposal,
        revision_number=(parent.revision_number + 1 if parent else 1),
        kind=kind,
        name=locked_proposal.name,
        items=deepcopy(locked_proposal.items),
        follow_up=follow_up,
        message=message,
        parent_revision=parent,
        created_by=created_by,
    )
    revision.full_clean()
    revision.save()
    return revision


def _catalog_publication_error():
    return EstimationProviderError(
        "The meal estimation provider returned catalog data that could not be published safely."
    )


def _published_text(value, *, max_length, allow_blank=False):
    if not isinstance(value, str):
        raise _catalog_publication_error()
    if UNSAFE_CATALOG_TEXT_PATTERN.search(value) or EMAIL_PATTERN.search(value):
        raise _catalog_publication_error()
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    if (not normalized and not allow_blank) or len(normalized) > max_length:
        raise _catalog_publication_error()
    return normalized


def _published_decimal(
    value,
    *,
    allow_null=False,
    positive=False,
    maximum=None,
):
    if value is None and allow_null:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise _catalog_publication_error() from error
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        raise _catalog_publication_error()
    if maximum is not None and parsed > Decimal(str(maximum)):
        raise _catalog_publication_error()
    return str(parsed)


def _published_source(source):
    if not isinstance(source, dict):
        raise _catalog_publication_error()
    title = _published_text(source.get("title"), max_length=200)
    provider = _published_text(
        source.get("provider", ""),
        max_length=160,
        allow_blank=True,
    )
    url = source.get("url")
    if (
        not isinstance(url, str)
        or len(url) > 500
        or any(character.isspace() or ord(character) < 32 for character in url)
    ):
        raise _catalog_publication_error()
    parsed_url = urlsplit(url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
    ):
        raise _catalog_publication_error()
    hostname = parsed_url.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(
        (".localhost", ".local", ".internal")
    ):
        raise _catalog_publication_error()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise _catalog_publication_error()
    return {
        "title": title,
        "provider": provider,
        "url": url,
        "accessed_on": source.get("accessed_on"),
    }


def _published_provider_item(item, *, depth=0):
    if not isinstance(item, dict) or depth > 8:
        raise _catalog_publication_error()
    components = item.get("components", [])
    sources = item.get("sources", [])
    nutrients = item.get("nutrients", {})
    if not isinstance(components, list) or len(components) > 30:
        raise _catalog_publication_error()
    if not isinstance(sources, list) or len(sources) > 20:
        raise _catalog_publication_error()
    if not isinstance(nutrients, dict) or set(nutrients) - set(NUTRIENT_FIELDS):
        raise _catalog_publication_error()

    origin_type = item.get("origin_type") or FoodItem.OriginType.GENERIC
    serving_unit = item.get("serving_unit") or FoodItemVersion.ServingUnit.SERVING
    provenance = item.get("provenance") or FoodItemVersion.Provenance.AI_ESTIMATE
    if origin_type not in FoodItem.OriginType.values:
        raise _catalog_publication_error()
    if serving_unit not in FoodItemVersion.ServingUnit.values:
        raise _catalog_publication_error()
    if provenance not in {
        FoodItemVersion.Provenance.OFFICIAL,
        FoodItemVersion.Provenance.AI_ESTIMATE,
    }:
        raise _catalog_publication_error()

    provider_name = _published_text(
        item.get("provider_name", ""),
        max_length=160,
        allow_blank=True,
    )
    if (
        origin_type in {FoodItem.OriginType.BRANDED, FoodItem.OriginType.RESTAURANT}
        and not provider_name
    ):
        raise _catalog_publication_error()

    nutrient_limits = {
        "calories": 10000,
        "protein": 2000,
        "carbohydrates": 2000,
        "fat": 2000,
        "fiber": 2000,
        "sugar": 2000,
        "sodium": 100000,
        "cholesterol": 100000,
    }
    safe_nutrients = {
        field: _published_decimal(
            nutrients.get(field),
            allow_null=True,
            maximum=nutrient_limits[field],
        )
        for field in NUTRIENT_FIELDS
    }
    confidence = _published_decimal(
        item.get("confidence_score"),
        allow_null=True,
        maximum=1,
    )
    key = item.get("key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", key):
        raise _catalog_publication_error()
    safe_sources = [_published_source(source) for source in sources]
    source_urls = [source["url"] for source in safe_sources]
    if len(source_urls) != len(set(source_urls)):
        raise _catalog_publication_error()

    return {
        "key": key,
        "name": _published_text(item.get("name"), max_length=200),
        "provider_name": provider_name,
        "origin_type": origin_type,
        "servings": _published_decimal(
            item.get("servings", "1"),
            positive=True,
            maximum=1000,
        ),
        "serving_quantity": _published_decimal(
            item.get("serving_quantity", "1"),
            positive=True,
            maximum=100000,
        ),
        "serving_unit": serving_unit,
        "serving_label": _published_text(
            item.get("serving_label") or "one serving",
            max_length=120,
        ),
        "serving_weight_grams": _published_decimal(
            item.get("serving_weight_grams"),
            allow_null=True,
            positive=True,
            maximum=100000,
        ),
        "serving_volume_ml": _published_decimal(
            item.get("serving_volume_ml"),
            allow_null=True,
            positive=True,
            maximum=100000,
        ),
        "provenance": provenance,
        "confidence_score": confidence,
        "nutrients": safe_nutrients,
        "sources": safe_sources,
        "components": [
            _published_provider_item(component, depth=depth + 1)
            for component in components
        ],
    }


def _fingerprint_decimal(value, *, decimal_places, default="0"):
    return str(_storage_decimal(value, decimal_places=decimal_places, default=default))


def _shared_fingerprint(*, item, components):
    payload = {
        "name": " ".join(item["name"].casefold().split()),
        "provider_name": " ".join(item.get("provider_name", "").casefold().split()),
        "origin_type": item.get("origin_type") or FoodItem.OriginType.GENERIC,
        "serving_quantity": _fingerprint_decimal(
            item.get("serving_quantity"), decimal_places=3, default="1"
        ),
        "serving_unit": item.get("serving_unit") or "serving",
        "serving_label": " ".join(item.get("serving_label", "").casefold().split()),
        "serving_weight_grams": (
            _fingerprint_decimal(item.get("serving_weight_grams"), decimal_places=3)
            if item.get("serving_weight_grams") is not None
            else None
        ),
        "serving_volume_ml": (
            _fingerprint_decimal(item.get("serving_volume_ml"), decimal_places=3)
            if item.get("serving_volume_ml") is not None
            else None
        ),
        "nutrients": {
            field: (
                _fingerprint_decimal(value, decimal_places=4)
                if value is not None
                else None
            )
            for field in NUTRIENT_FIELDS
            for value in [item.get("nutrients", {}).get(field)]
        },
        "components": [
            {
                "fingerprint": component["food_item"].shared_fingerprint,
                "version": component["food_version"].pk,
                "servings": str(component["servings"]),
                "order": component["order"],
            }
            for component in components
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _shared_definition(*, item, components, estimate):
    definition = _definition(item, components)
    definition.update(
        {
            "estimation_provider": estimate["provider_name"],
            "estimation_model": estimate["provider_model"],
            "estimation_response_id": estimate["provider_response_id"],
        }
    )
    return definition


def _materialize_shared_item(*, item, estimate):
    components = []
    for order, component_item in enumerate(item.get("components", [])):
        child_food, child_version = _materialize_shared_item(
            item=component_item,
            estimate=estimate,
        )
        components.append(
            {
                "food_item": child_food,
                "food_version": child_version,
                "servings": _storage_decimal(
                    component_item.get("servings"),
                    decimal_places=4,
                    default="1",
                ),
                "order": order,
            }
        )

    fingerprint = _shared_fingerprint(item=item, components=components)
    existing = (
        FoodItem.objects.active()
        .filter(
            scope=FoodItem.Scope.SHARED,
            shared_fingerprint=fingerprint,
            current_version__isnull=False,
        )
        .select_related("current_version")
        .first()
    )
    if existing:
        return existing, existing.current_version

    try:
        with transaction.atomic():
            food = create_food_item(
                name=item["name"],
                scope=FoodItem.Scope.SHARED,
                origin_type=item.get("origin_type") or FoodItem.OriginType.GENERIC,
                provider_name=item.get("provider_name", ""),
                owner=None,
                definition=_shared_definition(
                    item=item,
                    components=components,
                    estimate=estimate,
                ),
                created_by=None,
                shared_fingerprint=fingerprint,
            )
    except IntegrityError as error:
        food = (
            FoodItem.objects.filter(
                scope=FoodItem.Scope.SHARED,
                shared_fingerprint=fingerprint,
                current_version__isnull=False,
            )
            .select_related("current_version")
            .first()
        )
        if food is None:
            raise _catalog_publication_error() from error
    return food, food.current_version


def _shared_estimate_items(estimate):
    if (
        not isinstance(estimate.get("items"), list)
        or not estimate["items"]
        or len(estimate["items"]) > 20
    ):
        raise _catalog_publication_error()
    normalized = normalize_items(
        [_published_provider_item(item) for item in estimate["items"]]
    )
    result = []
    for item in normalized:
        food, version = _materialize_shared_item(item=item, estimate=estimate)
        result.append(
            _catalog_food(
                version,
                servings=item.get("servings", "1"),
                key=item["key"],
            )
        )
    return result


def _semantic_food_identity(item):
    return (
        "".join(_identity_tokens(item.get("provider_name", ""))),
        "".join(_identity_tokens(item.get("name", ""))),
        item.get("origin_type") or FoodItem.OriginType.GENERIC,
    )


@transaction.atomic
def create_proposal(*, owner, description, entry_date):
    description = description.strip()
    resolution = resolve_catalog_matches(description=description, user=owner)
    provider = None
    intent_name = ""
    if resolution["unmatched_description"]:
        provider = get_estimation_provider()
        try:
            search_plan = provider.extract_intents(description)
        except (AttributeError, EstimationProviderError):
            search_plan = None
        if isinstance(search_plan, dict):
            intent_name = _brief_generated_meal_name(search_plan.get("name"))
        intents = _validated_search_intents(search_plan)
        if intents:
            resolution = resolve_catalog_intents(intents=intents, user=owner)
    matches = resolution["matches"]
    catalog_items = [
        _catalog_food(
            match["food"].current_version,
            servings=match["servings"],
        )
        for match in matches
    ]
    if matches and not resolution["unmatched_description"]:
        confidence_values = [
            match["food"].current_version.confidence_score
            for match in matches
            if match["food"].current_version.confidence_score is not None
        ]
        proposal = MealProposal.objects.create(
            owner=owner,
            description=description,
            entry_date=entry_date,
            name=(
                intent_name
                or (matches[0]["food"].name if len(matches) == 1 else description[:120])
            ),
            generator=MealProposal.Generator.CATALOG,
            provider_name="MacroMapper catalog",
            confidence_score=(min(confidence_values) if confidence_values else None),
            items=catalog_items,
        )
        create_proposal_revision(
            proposal=proposal,
            kind=MealProposalRevision.Kind.GENERATED,
            created_by=None,
        )
        return proposal

    provider = provider or get_estimation_provider()
    estimate = provider.estimate(resolution["unmatched_description"] or description)
    estimated_items = _shared_estimate_items(estimate)
    catalog_identities = {_semantic_food_identity(item) for item in catalog_items}
    estimated_items = [
        item
        for item in estimated_items
        if _semantic_food_identity(item) not in catalog_identities
    ]
    items = [*catalog_items, *estimated_items]
    confidence_values = [
        *[
            match["food"].current_version.confidence_score
            for match in matches
            if match["food"].current_version.confidence_score is not None
        ],
        estimate["confidence_score"],
    ]
    proposal = MealProposal.objects.create(
        owner=owner,
        description=description,
        entry_date=entry_date,
        name=intent_name or _brief_generated_meal_name(estimate["name"]),
        generator=MealProposal.Generator.OPENAI,
        provider_name=(
            f"MacroMapper catalog + {estimate['provider_name']}"
            if catalog_items
            else estimate["provider_name"]
        ),
        provider_model=estimate["provider_model"],
        provider_response_id=estimate["provider_response_id"],
        confidence_score=min(confidence_values),
        items=items,
    )
    create_proposal_revision(
        proposal=proposal,
        kind=MealProposalRevision.Kind.GENERATED,
        created_by=None,
    )
    return proposal


def _follow_up_identity(item):
    if item.get("food_item_id"):
        return ("food_item", str(item["food_item_id"]))
    return _semantic_food_identity(item)


def _rekey_follow_up_item(item, *, key):
    item = deepcopy(item)
    item["key"] = key
    item["components"] = [
        _rekey_follow_up_item(component, key=f"{key}.{index}")
        for index, component in enumerate(item.get("components", []))
    ]
    return item


def _follow_up_search_intent(item):
    search = item.get("_catalog_search")
    if not isinstance(search, dict):
        search = {}
    provider_name = str(
        search.get("provider_name") or item.get("provider_name", "")
    ).strip()
    search_name = str(search.get("search_name") or item.get("name", "")).strip()
    raw_text = " ".join(value for value in (search_name, provider_name) if value)
    intents = _validated_search_intents(
        {
            "items": [
                {
                    "raw_text": raw_text,
                    "search_name": search_name,
                    "provider_name": provider_name,
                    "quantity": item.get("servings", search.get("quantity", 1)),
                    "defining_terms": search.get("defining_terms", []),
                    "aliases": search.get("aliases", []),
                }
            ]
        }
    )
    return intents[0] if intents else None


@transaction.atomic
def apply_proposal_follow_up(*, proposal, owner, follow_up, items, result):
    proposal = (
        MealProposal.objects.select_for_update()
        .prefetch_related("revisions")
        .get(pk=proposal.pk, owner=owner)
    )
    if proposal.status != MealProposal.Status.DRAFT:
        raise ValidationError("Accepted proposals cannot receive follow-up changes.")

    current_items = deepcopy(items)
    current_by_key = {item["key"]: item for item in current_items}
    remove_keys = set(result["remove_keys"])
    serving_updates = {}
    for update in result["serving_updates"]:
        key = update["key"]
        serving_updates[key] = update["servings"]

    remove_keys &= set(current_by_key)
    serving_updates = {
        key: servings
        for key, servings in serving_updates.items()
        if key in current_by_key and key not in remove_keys
    }

    retained_items = [item for item in current_items if item["key"] not in remove_keys]
    for item in retained_items:
        if item["key"] in serving_updates:
            item["servings"] = str(
                _storage_decimal(
                    serving_updates[item["key"]],
                    decimal_places=4,
                    default="1",
                )
            )

    existing_identities = {_follow_up_identity(item) for item in retained_items}
    retained_by_identity = {_follow_up_identity(item): item for item in retained_items}
    items_by_identity = dict(retained_by_identity)
    next_revision_number = len(proposal.revisions.all()) + 1
    foods = _visible_catalog_foods(owner)
    pending_additions = []
    merged_addition = False
    for index, item in enumerate(result["items_to_add"]):
        intent = _follow_up_search_intent(item)
        catalog_match = (
            _resolve_catalog_intent(intent=intent, user=owner, foods=foods)
            if intent
            else None
        )
        if catalog_match:
            candidate_item = _catalog_food(
                catalog_match["food"].current_version,
                servings=item.get("servings", "1"),
            )
            is_catalog_item = True
        else:
            candidate_item = deepcopy(item)
            candidate_item.pop("_catalog_search", None)
            is_catalog_item = False

        identity = _follow_up_identity(candidate_item)
        if identity in existing_identities:
            existing_item = items_by_identity[identity]
            existing_item["servings"] = str(
                _storage_decimal(
                    _decimal(existing_item["servings"], default="1")
                    + _decimal(candidate_item.get("servings"), default="1"),
                    decimal_places=4,
                    default="1",
                )
            )
            merged_addition = True
            continue
        existing_identities.add(identity)
        added_item = _rekey_follow_up_item(
            candidate_item,
            key=f"follow-up-{next_revision_number}-{index}",
        )
        pending_additions.append((is_catalog_item, added_item))
        items_by_identity[identity] = added_item

    if len(retained_items) + len(pending_additions) > 20:
        raise ValidationError("A proposal may contain at most 20 foods.")
    if not retained_items and not pending_additions:
        raise ValidationError("Keep at least one food in the proposal.")

    raw_additions = [item for is_catalog, item in pending_additions if not is_catalog]
    materialized_raw_additions = []
    if raw_additions:
        materialized_raw_additions = _shared_estimate_items(
            {
                "items": raw_additions,
                "provider_name": result["provider_name"],
                "provider_model": result["provider_model"],
                "provider_response_id": result["provider_response_id"],
            }
        )
    materialized_raw = iter(materialized_raw_additions)
    added_items = [
        item if is_catalog else next(materialized_raw)
        for is_catalog, item in pending_additions
    ]

    if (
        not remove_keys
        and not serving_updates
        and not added_items
        and not merged_addition
    ):
        return {
            "applied": False,
            "message": "AI could not produce an applicable meal change from that request.",
            "proposal": proposal,
        }

    proposal.name = _brief_generated_meal_name(result["name"])
    proposal.items = normalize_items([*retained_items, *added_items])
    proposal.generator = MealProposal.Generator.OPENAI
    provider_name = result["provider_name"]
    if proposal.provider_name and provider_name not in proposal.provider_name:
        proposal.provider_name = f"{proposal.provider_name} + {provider_name}"[:80]
    elif not proposal.provider_name:
        proposal.provider_name = provider_name
    proposal.provider_model = result["provider_model"]
    proposal.provider_response_id = result["provider_response_id"]
    follow_up_confidence = _storage_decimal(
        result["confidence_score"],
        decimal_places=3,
    )
    proposal.confidence_score = (
        min(proposal.confidence_score, follow_up_confidence)
        if proposal.confidence_score is not None
        else follow_up_confidence
    )
    proposal.save(
        update_fields=[
            "name",
            "items",
            "generator",
            "provider_name",
            "provider_model",
            "provider_response_id",
            "confidence_score",
            "updated_at",
        ]
    )
    create_proposal_revision(
        proposal=proposal,
        kind=MealProposalRevision.Kind.AI_FOLLOW_UP,
        created_by=owner,
        follow_up=follow_up,
        message=result["message"],
    )
    return {
        "applied": True,
        "message": result["message"],
        "proposal": proposal,
    }


def _visible_catalog_version(*, owner, item):
    food_item_id = item.get("food_item_id")
    version_id = item.get("food_version_id")
    if not food_item_id or not version_id:
        return None
    return (
        FoodItemVersion.objects.filter(
            pk=version_id,
            food_item_id=food_item_id,
            food_item__archived_at__isnull=True,
        )
        .filter(Q(food_item__scope=FoodItem.Scope.SHARED) | Q(food_item__owner=owner))
        .select_related("food_item")
        .first()
    )


def secure_review_items(*, proposal, owner, items):
    """Keep provenance immutable while accepting quantity and nutrient edits."""

    existing = _items_by_key(proposal.items)

    def secure(item, *, depth=0):
        original = existing.get(item["key"])
        if original is None:
            if depth:
                raise ValidationError(
                    "New ingredients must be added as top-level catalog foods."
                )
            version = _visible_catalog_version(owner=owner, item=item)
            if version is None:
                raise ValidationError(
                    "New proposal foods must come from your visible catalog."
                )
            result = _catalog_food(
                version,
                servings=item["servings"],
                key=item["key"],
            )
            selected_portion_key = item["selected_portion_key"]
            if selected_portion_key not in {
                option["key"] for option in result["portion_options"]
            }:
                raise ValidationError("Choose an available portion option.")
            result["selected_portion_key"] = selected_portion_key
            result["nutrients"] = item["nutrients"]
            return result

        result = dict(original)
        result["portion_options"] = _portion_options(original)
        selected_portion_key = item["selected_portion_key"]
        if selected_portion_key not in {
            option["key"] for option in result["portion_options"]
        }:
            raise ValidationError("Choose an available portion option.")
        result["selected_portion_key"] = selected_portion_key
        result["servings"] = item["servings"]
        result["nutrients"] = item["nutrients"]
        requested_components = item.get("components", [])
        original_component_keys = {
            component["key"] for component in original.get("components", [])
        }
        if any(
            component["key"] not in original_component_keys
            for component in requested_components
        ):
            raise ValidationError(
                "New ingredients must be added from the catalog, not inserted into a component tree."
            )
        result["components"] = [
            secure(component, depth=depth + 1) for component in requested_components
        ]
        if original.get("components") and not result["components"]:
            result["nutrients"] = {field: None for field in NUTRIENT_FIELDS}
        return result

    reviewed = normalize_items([secure(item) for item in items])
    return _apply_review_attribution(items=reviewed, owner=owner)


def _definition(item, components):
    nutrients = {
        field: _storage_decimal(value, decimal_places=4)
        for field in NUTRIENT_FIELDS
        if (value := item.get("nutrients", {}).get(field)) is not None
    }
    confidence = item.get("confidence_score")
    return {
        "serving_quantity": _storage_decimal(
            item.get("serving_quantity"), decimal_places=3, default="1"
        ),
        "serving_unit": item.get("serving_unit") or "serving",
        "serving_label": item.get("serving_label") or "one serving",
        "serving_weight_grams": (
            _storage_decimal(item.get("serving_weight_grams"), decimal_places=3)
            if item.get("serving_weight_grams") is not None
            else None
        ),
        "serving_volume_ml": (
            _storage_decimal(item.get("serving_volume_ml"), decimal_places=3)
            if item.get("serving_volume_ml") is not None
            else None
        ),
        "provenance": item.get("provenance") or FoodItemVersion.Provenance.AI_ESTIMATE,
        "confidence_score": (
            _storage_decimal(confidence, decimal_places=3)
            if confidence is not None
            else None
        ),
        "nutrients": nutrients,
        "sources": [
            {
                "title": source["title"],
                "provider": source.get("provider", ""),
                "url": source["url"],
                "accessed_on": source.get("accessed_on"),
            }
            for source in item.get("sources", [])
        ],
        "components": components,
    }


def _matches_catalog_nutrients(item, version):
    catalog_nutrients = _effective_nutrients(version)
    requested_nutrients = item.get("nutrients", {})
    for field in NUTRIENT_FIELDS:
        catalog_value = catalog_nutrients.get(field)
        requested_value = requested_nutrients.get(field)
        if catalog_value is None or requested_value is None:
            if catalog_value is not None or requested_value is not None:
                return False
            continue
        if _storage_decimal(catalog_value, decimal_places=4) != _storage_decimal(
            requested_value, decimal_places=4
        ):
            return False
    return True


def _matches_catalog_value(value, stored, *, decimal_places):
    if value is None or stored is None:
        return value is None and stored is None
    return _storage_decimal(value, decimal_places=decimal_places) == _storage_decimal(
        stored, decimal_places=decimal_places
    )


def _matches_catalog_tree(item, version):
    if not _matches_catalog_nutrients(item, version):
        return False
    if not _matches_catalog_value(
        item.get("serving_quantity"),
        version.serving_quantity,
        decimal_places=3,
    ):
        return False
    if item.get("serving_unit") != version.serving_unit:
        return False
    if item.get("serving_label", "") != version.serving_label:
        return False
    if not _matches_catalog_value(
        item.get("serving_weight_grams"),
        version.serving_weight_grams,
        decimal_places=3,
    ):
        return False
    if not _matches_catalog_value(
        item.get("serving_volume_ml"),
        version.serving_volume_ml,
        decimal_places=3,
    ):
        return False

    requested_components = item.get("components", [])
    catalog_components = list(
        version.components.select_related("child_version__food_item").all()
    )
    if len(requested_components) != len(catalog_components):
        return False
    for requested, catalog in zip(
        requested_components, catalog_components, strict=True
    ):
        if requested.get("food_item_id") != catalog.child_version.food_item_id:
            return False
        if requested.get("food_version_id") != catalog.child_version_id:
            return False
        if not _matches_catalog_value(
            requested.get("servings"), catalog.servings, decimal_places=4
        ):
            return False
        if not _matches_catalog_tree(requested, catalog.child_version):
            return False
    return True


def _apply_review_attribution(*, items, owner):
    def annotate(item):
        item = dict(item)
        item["components"] = [
            annotate(component) for component in item.get("components", [])
        ]
        version = _visible_catalog_version(owner=owner, item=item)
        modified = version is not None and not _matches_catalog_tree(item, version)
        item["is_user_modified"] = modified
        if modified:
            item["provenance"] = FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE
            item["source_kind"] = "user_modified_estimate"
            item["confidence_score"] = None
        elif version is not None:
            item["provenance"] = version.provenance
            item["source_kind"] = _source_kind(version.provenance)
            item["confidence_score"] = (
                str(version.confidence_score)
                if version.confidence_score is not None
                else None
            )
        return item

    return [annotate(item) for item in items]


def _matches_materialized_components(version, components):
    catalog_components = list(
        version.components.select_related("child_version__food_item").all()
    )
    if len(components) != len(catalog_components):
        return False
    for materialized, catalog in zip(components, catalog_components, strict=True):
        if materialized["food_version"].pk != catalog.child_version_id:
            return False
        if not _matches_catalog_value(
            materialized["servings"], catalog.servings, decimal_places=4
        ):
            return False
    return True


def _materialize_item(*, owner, item):
    components = []
    for order, component_item in enumerate(item.get("components", [])):
        child_food, child_version = _materialize_item(owner=owner, item=component_item)
        components.append(
            {
                "food_item": child_food,
                "food_version": child_version,
                "servings": _storage_decimal(
                    component_item.get("servings"),
                    decimal_places=4,
                    default="1",
                ),
                "order": order,
            }
        )

    catalog_version = _visible_catalog_version(owner=owner, item=item)
    if (
        catalog_version is not None
        and _matches_catalog_nutrients(item, catalog_version)
        and _matches_materialized_components(catalog_version, components)
    ):
        return catalog_version.food_item, catalog_version

    origin_type = item.get("origin_type") or FoodItem.OriginType.GENERIC
    provider_name = item.get("provider_name", "")
    if (
        origin_type
        in {
            FoodItem.OriginType.BRANDED,
            FoodItem.OriginType.RESTAURANT,
        }
        and not provider_name.strip()
    ):
        origin_type = FoodItem.OriginType.GENERIC
    definition = _definition(item, components)
    if catalog_version is not None:
        definition["provenance"] = FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE
        definition["confidence_score"] = None
        definition["derived_from"] = catalog_version
        definition["estimation_provider"] = catalog_version.estimation_provider
        definition["estimation_model"] = catalog_version.estimation_model
        definition["estimation_response_id"] = catalog_version.estimation_response_id
    food = create_food_item(
        name=item["name"],
        scope=FoodItem.Scope.PERSONAL,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=owner,
        definition=definition,
        created_by=owner,
    )
    return food, food.current_version


@transaction.atomic
def accept_proposal(*, proposal):
    proposal = MealProposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.status != MealProposal.Status.DRAFT:
        raise ValidationError("This proposal has already been accepted.")
    items = _apply_review_attribution(
        items=normalize_items(proposal.items), owner=proposal.owner
    )
    if not items:
        raise ValidationError("Add at least one food before saving this meal.")

    follow_up_requests = list(
        proposal.revisions.filter(kind=MealProposalRevision.Kind.AI_FOLLOW_UP)
        .exclude(follow_up="")
        .order_by("revision_number", "id")
        .values_list("follow_up", flat=True)
    )
    notes = f"Estimated from: {proposal.description}"
    if follow_up_requests:
        notes += "\n\nAI follow-ups:\n" + "\n".join(
            f"- {request}" for request in follow_up_requests
        )

    meal = MealEntry.objects.create(
        owner=proposal.owner,
        entry_date=proposal.entry_date,
        name=proposal.name,
        notes=notes,
    )
    item_inputs = []
    for order, item in enumerate(items):
        food, version = _materialize_item(owner=proposal.owner, item=item)
        item_inputs.append(
            {
                "food_item": food,
                "food_version": version.pk,
                "servings": _storage_decimal(
                    item.get("servings"), decimal_places=4, default="1"
                ),
                "order": order,
            }
        )
    replace_meal_items(meal_entry=meal, item_inputs=item_inputs)
    proposal.items = items
    proposal.status = MealProposal.Status.ACCEPTED
    proposal.accepted_meal = meal
    proposal.accepted_at = timezone.now()
    proposal.save(
        update_fields=["items", "status", "accepted_meal", "accepted_at", "updated_at"]
    )
    create_proposal_revision(
        proposal=proposal,
        kind=MealProposalRevision.Kind.ACCEPTED,
        created_by=proposal.owner,
    )
    return meal
