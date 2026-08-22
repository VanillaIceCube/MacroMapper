from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from rest_framework import serializers

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS

from .models import MealProposal
from .services import create_proposal, normalize_items, secure_review_items

SOURCE_KINDS = {"official_verified", "catalog_estimate", "ai_estimate"}
ITEM_FIELDS = {
    "key",
    "food_item_id",
    "food_version_id",
    "name",
    "provider_name",
    "origin_type",
    "servings",
    "serving_quantity",
    "serving_unit",
    "serving_label",
    "provenance",
    "source_kind",
    "confidence_score",
    "nutrients",
    "sources",
    "components",
}


def _decimal(value, *, field, allow_null=False, positive=False):
    if value is None and allow_null:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise serializers.ValidationError({field: "Supply a valid number."}) from error
    if parsed < 0 or (positive and parsed <= 0):
        raise serializers.ValidationError(
            {
                field: "Supply a positive number."
                if positive
                else "Must be zero or greater."
            }
        )
    return str(parsed)


def _validate_source(source):
    if not isinstance(source, dict):
        raise serializers.ValidationError("Each source must be an object.")
    title = str(source.get("title", "")).strip()
    if not title or len(title) > 200:
        raise serializers.ValidationError(
            "Each source needs a title of 200 characters or fewer."
        )
    url = str(source.get("url", "")).strip()
    try:
        URLValidator(schemes=["http", "https"])(url)
    except Exception as error:
        raise serializers.ValidationError(
            "Each source needs a valid HTTP(S) URL."
        ) from error
    provider = str(source.get("provider", "")).strip()
    if len(provider) > 160:
        raise serializers.ValidationError(
            "Source providers must be 160 characters or fewer."
        )
    return {
        "title": title,
        "provider": provider,
        "url": url,
        "accessed_on": source.get("accessed_on"),
        "is_official": bool(source.get("is_official", False)),
    }


def _validate_item(item, *, depth=0, seen_keys=None):
    if depth > 4:
        raise serializers.ValidationError(
            "Proposal components may be at most five levels deep."
        )
    if not isinstance(item, dict):
        raise serializers.ValidationError("Each proposed food must be an object.")
    unknown = set(item) - ITEM_FIELDS
    if unknown:
        raise serializers.ValidationError(
            f"Unsupported proposal fields: {', '.join(sorted(unknown))}."
        )
    name = str(item.get("name", "")).strip()
    if not name or len(name) > 200:
        raise serializers.ValidationError(
            "Each proposed food needs a name of 200 characters or fewer."
        )
    key = str(item.get("key", "")).strip()
    if not key or len(key) > 160:
        raise serializers.ValidationError("Each proposed food needs a stable key.")
    seen_keys = seen_keys if seen_keys is not None else set()
    if key in seen_keys:
        raise serializers.ValidationError("Each proposed food key must be unique.")
    seen_keys.add(key)

    origin_type = item.get("origin_type", FoodItem.OriginType.GENERIC)
    if origin_type not in FoodItem.OriginType.values:
        raise serializers.ValidationError("A proposed food has an invalid origin type.")
    serving_unit = item.get("serving_unit", FoodItemVersion.ServingUnit.SERVING)
    if serving_unit not in FoodItemVersion.ServingUnit.values:
        raise serializers.ValidationError(
            "A proposed food has an invalid serving unit."
        )
    provenance = item.get("provenance", FoodItemVersion.Provenance.AI_ESTIMATE)
    if provenance not in FoodItemVersion.Provenance.values:
        raise serializers.ValidationError("A proposed food has invalid provenance.")
    source_kind = item.get("source_kind", "ai_estimate")
    if source_kind not in SOURCE_KINDS:
        raise serializers.ValidationError(
            "A proposed food has an invalid source label."
        )

    food_item_id = item.get("food_item_id")
    food_version_id = item.get("food_version_id")
    if bool(food_item_id) != bool(food_version_id):
        raise serializers.ValidationError(
            "Catalog food and version identifiers must be supplied together."
        )
    if food_item_id is not None and (
        not isinstance(food_item_id, int) or not isinstance(food_version_id, int)
    ):
        raise serializers.ValidationError("Catalog identifiers must be integers.")

    raw_nutrients = item.get("nutrients", {})
    if not isinstance(raw_nutrients, dict) or set(raw_nutrients) - set(NUTRIENT_FIELDS):
        raise serializers.ValidationError(
            "A proposed food contains unsupported nutrients."
        )
    nutrients = {
        field: _decimal(raw_nutrients.get(field), field=field, allow_null=True)
        for field in NUTRIENT_FIELDS
    }
    sources = item.get("sources", [])
    components = item.get("components", [])
    if not isinstance(sources, list) or len(sources) > 20:
        raise serializers.ValidationError(
            "A proposed food may retain at most 20 sources."
        )
    if not isinstance(components, list) or len(components) > 30:
        raise serializers.ValidationError(
            "A proposed food may contain at most 30 components."
        )
    confidence = _decimal(
        item.get("confidence_score"), field="confidence_score", allow_null=True
    )
    if confidence is not None and Decimal(confidence) > 1:
        raise serializers.ValidationError("Confidence must be between zero and one.")

    return {
        "key": key,
        "food_item_id": food_item_id,
        "food_version_id": food_version_id,
        "name": name,
        "provider_name": str(item.get("provider_name", "")).strip()[:160],
        "origin_type": origin_type,
        "servings": _decimal(
            item.get("servings", "1"), field="servings", positive=True
        ),
        "serving_quantity": _decimal(
            item.get("serving_quantity", "1"),
            field="serving_quantity",
            positive=True,
        ),
        "serving_unit": serving_unit,
        "serving_label": str(item.get("serving_label", ""))[:120],
        "provenance": provenance,
        "source_kind": source_kind,
        "confidence_score": confidence,
        "nutrients": nutrients,
        "sources": [_validate_source(source) for source in sources],
        "components": [
            _validate_item(component, depth=depth + 1, seen_keys=seen_keys)
            for component in components
        ],
    }


class ProposalItemsField(serializers.JSONField):
    def to_internal_value(self, data):
        if not isinstance(data, list) or not data:
            raise serializers.ValidationError("Add at least one food to the proposal.")
        if len(data) > 20:
            raise serializers.ValidationError(
                "A proposal may contain at most 20 foods."
            )
        seen_keys = set()
        return normalize_items(
            [_validate_item(item, seen_keys=seen_keys) for item in data]
        )


class MealProposalSerializer(serializers.ModelSerializer):
    items = ProposalItemsField(required=False)
    accepted_meal_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MealProposal
        fields = (
            "id",
            "description",
            "entry_date",
            "name",
            "status",
            "generator",
            "provider_name",
            "provider_model",
            "provider_response_id",
            "confidence_score",
            "items",
            "accepted_meal_id",
            "accepted_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "generator",
            "provider_name",
            "provider_model",
            "provider_response_id",
            "confidence_score",
            "accepted_meal_id",
            "accepted_at",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "name": {"required": False},
            "description": {"max_length": 2000},
        }

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Describe the meal to estimate.")
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name the proposed meal.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            if self.instance.status != MealProposal.Status.DRAFT:
                raise serializers.ValidationError(
                    "Accepted proposals cannot be edited."
                )
            attrs.pop("description", None)
            attrs.pop("entry_date", None)
            if "items" in attrs:
                try:
                    attrs["items"] = secure_review_items(
                        proposal=self.instance,
                        owner=self.context["request"].user,
                        items=attrs["items"],
                    )
                except DjangoValidationError as error:
                    raise serializers.ValidationError(str(error)) from error
        return attrs

    def create(self, validated_data):
        return create_proposal(
            owner=self.context["request"].user,
            description=validated_data["description"],
            entry_date=validated_data["entry_date"],
        )
