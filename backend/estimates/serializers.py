from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import serializers

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS
from foods.portions import portion_options_for_serving

from .models import MealProposal, MealProposalRevision
from .services import (
    apply_proposal_follow_up,
    create_builder_proposal,
    create_proposal,
    create_proposal_revision,
    normalize_items,
    saved_meal_version_ids,
    secure_review_items,
)

SOURCE_KINDS = {
    "official_verified",
    "catalog_estimate",
    "ai_estimate",
    "user_modified_estimate",
    "user_entered",
}
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
    "serving_weight_grams",
    "serving_volume_ml",
    "portion_options",
    "selected_portion_key",
    "provenance",
    "source_kind",
    "confidence_score",
    "is_user_modified",
    "nutrients",
    "sources",
    "components",
}
PORTION_OPTION_FIELDS = {"key", "label", "unit_label", "serving_multiplier"}


def _decimal(value, *, field, allow_null=False, positive=False):
    if value is None and allow_null:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise serializers.ValidationError({field: "Supply a valid number."}) from error
    if not parsed.is_finite():
        raise serializers.ValidationError({field: "Supply a finite number."})
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


def _validate_portion_options(item, *, serving_quantity, serving_unit, serving_label):
    raw_options = item.get("portion_options") or portion_options_for_serving(
        quantity=serving_quantity,
        unit=serving_unit,
        label=serving_label,
    )
    if not isinstance(raw_options, list) or len(raw_options) > 12:
        raise serializers.ValidationError(
            "A proposed food may contain at most 12 portion options."
        )

    options = []
    option_keys = set()
    for option in raw_options:
        if not isinstance(option, dict) or set(option) - PORTION_OPTION_FIELDS:
            raise serializers.ValidationError(
                "Each portion option must contain only supported fields."
            )
        key = str(option.get("key", "")).strip()
        label = str(option.get("label", "")).strip()
        unit_label = str(option.get("unit_label", "")).strip()
        if not key or len(key) > 40 or key in option_keys:
            raise serializers.ValidationError(
                "Each portion option needs a unique key of 40 characters or fewer."
            )
        if not label or len(label) > 80:
            raise serializers.ValidationError(
                "Each portion option needs a label of 80 characters or fewer."
            )
        if not unit_label or len(unit_label) > 32:
            raise serializers.ValidationError(
                "Each portion option needs a unit label of 32 characters or fewer."
            )
        option_keys.add(key)
        options.append(
            {
                "key": key,
                "label": label,
                "unit_label": unit_label,
                "serving_multiplier": _decimal(
                    option.get("serving_multiplier"),
                    field="serving_multiplier",
                    positive=True,
                ),
            }
        )

    selected_key = str(item.get("selected_portion_key", "")).strip()
    if not selected_key:
        selected_key = options[0]["key"]
    if selected_key not in option_keys:
        raise serializers.ValidationError("Choose an available portion option.")
    return options, selected_key


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
    serving_quantity = _decimal(
        item.get("serving_quantity", "1"),
        field="serving_quantity",
        positive=True,
    )
    serving_label = str(item.get("serving_label", ""))[:120]
    serving_weight_grams = _decimal(
        item.get("serving_weight_grams"),
        field="serving_weight_grams",
        allow_null=True,
        positive=True,
    )
    serving_volume_ml = _decimal(
        item.get("serving_volume_ml"),
        field="serving_volume_ml",
        allow_null=True,
        positive=True,
    )
    portion_options, selected_portion_key = _validate_portion_options(
        item,
        serving_quantity=serving_quantity,
        serving_unit=serving_unit,
        serving_label=serving_label,
    )

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
        "serving_quantity": serving_quantity,
        "serving_unit": serving_unit,
        "serving_label": serving_label,
        "serving_weight_grams": serving_weight_grams,
        "serving_volume_ml": serving_volume_ml,
        "portion_options": portion_options,
        "selected_portion_key": selected_portion_key,
        "provenance": provenance,
        "source_kind": source_kind,
        "confidence_score": confidence,
        "is_user_modified": bool(item.get("is_user_modified", False)),
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


class MapYourMealItemsField(serializers.JSONField):
    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("Meal items must be a list.")
        if len(data) > 20:
            raise serializers.ValidationError("A meal may contain at most 20 foods.")
        seen_keys = set()
        return normalize_items(
            [_validate_item(item, seen_keys=seen_keys) for item in data]
        )


class MapYourMealDraftSerializer(serializers.Serializer):
    entry_date = serializers.DateField()
    name = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
        allow_blank=True,
        required=False,
    )
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    items = ProposalItemsField()

    def validate_name(self, value):
        if self.context.get("meal") is not None and not value:
            raise serializers.ValidationError("Name the meal before saving changes.")
        return value


class MealProposalFollowUpSerializer(serializers.Serializer):
    follow_up = serializers.CharField(max_length=500, trim_whitespace=True)
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    entry_date = serializers.DateField(required=False)
    items = ProposalItemsField()

    def validate_follow_up(self, value):
        if not value:
            raise serializers.ValidationError("Describe what should change.")
        return value

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Name the proposed meal.")
        return value

    def validate(self, attrs):
        proposal = self.context["proposal"]
        if proposal.status != MealProposal.Status.DRAFT:
            raise serializers.ValidationError(
                "Accepted proposals cannot receive follow-up changes."
            )
        try:
            attrs["items"] = secure_review_items(
                proposal=proposal,
                owner=self.context["request"].user,
                items=attrs["items"],
            )
        except DjangoValidationError:
            raise serializers.ValidationError(
                "Current proposal edits could not be validated."
            ) from None
        return attrs

    def apply(self, result):
        return apply_proposal_follow_up(
            proposal=self.context["proposal"],
            owner=self.context["request"].user,
            follow_up=self.validated_data["follow_up"],
            notes=self.validated_data.get("notes", self.context["proposal"].notes),
            entry_date=self.validated_data.get(
                "entry_date", self.context["proposal"].entry_date
            ),
            items=self.validated_data["items"],
            result=result,
        )


class MapYourMealAdjustmentSerializer(serializers.Serializer):
    adjustment = serializers.CharField(max_length=500, trim_whitespace=True)
    entry_date = serializers.DateField()
    name = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
        allow_blank=True,
        required=False,
    )
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    items = MapYourMealItemsField()

    def validate_adjustment(self, value):
        if not value:
            raise serializers.ValidationError("Describe what should change.")
        return value

    def create_proposal(self):
        meal = self.context.get("meal")
        return create_builder_proposal(
            owner=self.context["request"].user,
            entry_date=self.validated_data["entry_date"],
            name=self.validated_data.get("name", ""),
            notes=self.validated_data.get("notes", ""),
            items=self.validated_data["items"],
            allowed_version_ids=(saved_meal_version_ids(meal) if meal else ()),
        )


class MealProposalRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealProposalRevision
        fields = (
            "id",
            "revision_number",
            "kind",
            "name",
            "notes",
            "items",
            "follow_up",
            "message",
            "parent_revision_id",
            "created_at",
        )


class MealProposalSerializer(serializers.ModelSerializer):
    items = ProposalItemsField(required=False)
    accepted_meal_id = serializers.IntegerField(read_only=True)
    revisions = MealProposalRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = MealProposal
        fields = (
            "id",
            "description",
            "entry_date",
            "name",
            "notes",
            "status",
            "generator",
            "provider_name",
            "provider_model",
            "provider_response_id",
            "confidence_score",
            "items",
            "revisions",
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
            "notes": {"required": False, "allow_blank": True, "max_length": 2000},
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

    def validate_notes(self, value):
        return value.strip()

    def validate(self, attrs):
        if self.instance is not None:
            if self.instance.status != MealProposal.Status.DRAFT:
                raise serializers.ValidationError(
                    "Accepted proposals cannot be edited."
                )
            attrs.pop("description", None)
            if "items" in attrs:
                try:
                    attrs["items"] = secure_review_items(
                        proposal=self.instance,
                        owner=self.context["request"].user,
                        items=attrs["items"],
                    )
                except DjangoValidationError:
                    raise serializers.ValidationError(
                        "Proposal edits could not be validated."
                    ) from None
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        create_proposal_revision(
            proposal=instance,
            kind=MealProposalRevision.Kind.USER_REVIEWED,
            created_by=self.context["request"].user,
        )
        return instance

    def create(self, validated_data):
        return create_proposal(
            owner=self.context["request"].user,
            description=validated_data["description"],
            entry_date=validated_data["entry_date"],
        )
