from collections.abc import Mapping
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .evidence import version_evidence
from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)
from .nutrients import NUTRIENT_METADATA
from .portions import clean_natural_servings, portion_options_for_version
from .services import create_personal_food, update_personal_food, validate_food_data


def _actor(context):
    return context.get("actor") or getattr(context.get("request"), "user", None)


class SourceReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceReference
        fields = (
            "id",
            "title",
            "provider",
            "url",
            "accessed_on",
            "is_official",
            "evidence",
        )
        read_only_fields = ("is_official", "evidence")


def _serialized_nutrients(version):
    return [
        {
            "key": key,
            "name": metadata["name"],
            "unit": metadata["unit"],
            "amount": f"{value:.4f}",
        }
        for key, metadata in NUTRIENT_METADATA.items()
        if (value := getattr(version, key)) is not None
    ]


def _selected_portion_key(version):
    return next(
        (
            option["key"]
            for option in portion_options_for_version(version)
            if option["key"].startswith("size:")
            and Decimal(option["serving_multiplier"]) == 1
        ),
        "base",
    )


def _components_for_version(version, context):
    component_map = context.get("component_map")
    if component_map is None:
        return version.components.select_related(
            "child_version__food_item"
        ).prefetch_related("child_version__sources")
    return component_map.get(version.pk, ())


class FoodComponentSerializer(serializers.ModelSerializer):
    natural_servings = serializers.JSONField(
        source="child_version.natural_servings", read_only=True
    )
    evidence = serializers.SerializerMethodField()

    def get_evidence(self, instance):
        return version_evidence(instance.child_version)

    food_item_id = serializers.IntegerField(source="child_version.food_item_id")
    food_item_name = serializers.CharField(source="child_version.food_item.name")
    food_version_id = serializers.IntegerField(source="child_version_id")
    provider_name = serializers.CharField(
        source="child_version.food_item.provider_name"
    )
    origin_type = serializers.CharField(source="child_version.food_item.origin_type")
    serving_quantity = serializers.DecimalField(
        source="child_version.serving_quantity",
        max_digits=10,
        decimal_places=3,
    )
    serving_unit = serializers.CharField(source="child_version.serving_unit")
    serving_label = serializers.CharField(source="child_version.serving_label")
    provenance = serializers.CharField(source="child_version.provenance")
    confidence_score = serializers.DecimalField(
        source="child_version.confidence_score",
        max_digits=4,
        decimal_places=3,
        allow_null=True,
    )
    nutrients = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    portion_options = serializers.SerializerMethodField()

    class Meta:
        model = FoodComponent
        fields = (
            "id",
            "food_item_id",
            "food_item_name",
            "food_version_id",
            "provider_name",
            "origin_type",
            "servings",
            "order",
            "serving_quantity",
            "serving_unit",
            "serving_label",
            "natural_servings",
            "portion_options",
            "provenance",
            "evidence",
            "confidence_score",
            "nutrients",
            "sources",
            "components",
        )

    def get_nutrients(self, instance):
        return _serialized_nutrients(instance.child_version)

    def get_sources(self, instance):
        return SourceReferenceSerializer(
            instance.child_version.sources.all(),
            many=True,
            context=self.context,
        ).data

    def get_components(self, instance):
        return FoodComponentSerializer(
            _components_for_version(instance.child_version, self.context),
            many=True,
            context=self.context,
        ).data

    def get_portion_options(self, instance):
        return portion_options_for_version(instance.child_version)


class FoodItemVersionSerializer(serializers.ModelSerializer):
    evidence = serializers.SerializerMethodField()

    def get_evidence(self, instance):
        return version_evidence(instance)

    nutrients = serializers.SerializerMethodField()
    sources = SourceReferenceSerializer(many=True, read_only=True)
    components = serializers.SerializerMethodField()
    portion_options = serializers.SerializerMethodField()
    selected_portion_key = serializers.SerializerMethodField()

    class Meta:
        model = FoodItemVersion
        fields = (
            "id",
            "version_number",
            "serving_quantity",
            "serving_unit",
            "serving_label",
            "natural_servings",
            "serving_weight_grams",
            "serving_volume_ml",
            "portion_options",
            "selected_portion_key",
            "provenance",
            "evidence",
            "confidence_score",
            "derived_from",
            "estimation_provider",
            "estimation_model",
            "nutrients",
            "sources",
            "components",
            "created_at",
        )

    def get_nutrients(self, instance):
        return _serialized_nutrients(instance)

    def get_components(self, instance):
        return FoodComponentSerializer(
            _components_for_version(instance, self.context),
            many=True,
            context=self.context,
        ).data

    def get_portion_options(self, instance):
        return portion_options_for_version(instance)

    def get_selected_portion_key(self, instance):
        return _selected_portion_key(instance)


class NutrientValuesInputSerializer(serializers.Serializer):
    calories = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    protein = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    carbohydrates = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    fat = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    fiber = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    sugar = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    sodium = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )
    cholesterol = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=0, required=False, allow_null=True
    )

    def to_internal_value(self, data):
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError(
                {
                    key: "This nutrient is not supported."
                    for key in sorted(unknown_fields)
                }
            )
        return super().to_internal_value(data)


class SourceReferenceInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    provider = serializers.CharField(max_length=160, required=False, allow_blank=True)
    url = serializers.URLField(max_length=500)
    accessed_on = serializers.DateField(required=False, allow_null=True)


class FoodItemReferenceSerializer(serializers.Serializer):
    food_item_id = serializers.PrimaryKeyRelatedField(
        source="food_item", queryset=FoodItem.objects.all()
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and "food_item" in data:
            raise serializers.ValidationError(
                {"food_item_id": "Use food_item_id for the catalog food reference."}
            )
        return super().to_internal_value(data)


class FoodComponentInputSerializer(FoodItemReferenceSerializer):
    servings = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    order = serializers.IntegerField(min_value=0, max_value=32767, default=0)

    def validate_food_item_id(self, food_item):
        actor = _actor(self.context)
        if (
            not actor
            or not FoodItem.objects.active()
            .visible_to(actor)
            .filter(pk=food_item.pk)
            .exists()
        ):
            raise serializers.ValidationError("This food is not available.")
        if food_item.current_version_id is None:
            raise serializers.ValidationError("This food has no current definition.")
        return food_item


class FoodDefinitionInputSerializer(serializers.Serializer):
    natural_servings = serializers.JSONField(required=False)

    def validate_natural_servings(self, value):
        try:
            return clean_natural_servings(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    serving_quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    serving_unit = serializers.ChoiceField(choices=FoodItemVersion.ServingUnit)
    serving_label = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    serving_weight_grams = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
        required=False,
        allow_null=True,
    )
    serving_volume_ml = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
        required=False,
        allow_null=True,
    )
    provenance = serializers.ChoiceField(choices=FoodItemVersion.Provenance)
    confidence_score = serializers.DecimalField(
        max_digits=4,
        decimal_places=3,
        min_value=0,
        max_value=1,
        required=False,
        allow_null=True,
    )
    nutrients = NutrientValuesInputSerializer(required=False)
    sources = SourceReferenceInputSerializer(many=True, required=False)
    components = FoodComponentInputSerializer(many=True, required=False)

    def validate(self, attrs):
        sources = attrs.get("sources", [])
        source_urls = [item["url"] for item in sources]
        if len(source_urls) != len(set(source_urls)):
            raise serializers.ValidationError(
                {"sources": "Each source URL may appear only once."}
            )

        components = attrs.get("components", [])
        component_ids = [item["food_item"].pk for item in components]
        if len(component_ids) != len(set(component_ids)):
            raise serializers.ValidationError(
                {"components": "Each component food may appear only once."}
            )
        orders = [item["order"] for item in components]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                {"components": "Each component order must be unique."}
            )
        return attrs


class FoodItemSerializer(serializers.ModelSerializer):
    current_version = FoodItemVersionSerializer(read_only=True)
    definition = FoodDefinitionInputSerializer(write_only=True, required=False)

    class Meta:
        model = FoodItem
        fields = (
            "id",
            "name",
            "scope",
            "origin_type",
            "provider_name",
            "market",
            "product_identifier",
            "identity_url",
            "merged_into",
            "current_version",
            "definition",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scope",
            "merged_into",
            "current_version",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        return validate_food_data(_actor(self.context), attrs, self.instance)

    def create(self, validated_data):
        return create_personal_food(_actor(self.context), validated_data)

    def update(self, instance, validated_data):
        return update_personal_food(_actor(self.context), instance, validated_data)
