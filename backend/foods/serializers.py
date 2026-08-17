from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)
from .nutrients import NUTRIENT_METADATA
from .services import create_food_item, create_food_version


class SourceReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceReference
        fields = ("id", "title", "provider", "url", "accessed_on")


class FoodComponentSerializer(serializers.ModelSerializer):
    food_item_id = serializers.IntegerField(source="child_version.food_item_id")
    food_item_name = serializers.CharField(source="child_version.food_item.name")
    food_version_id = serializers.IntegerField(source="child_version_id")
    serving_quantity = serializers.DecimalField(
        source="child_version.serving_quantity",
        max_digits=10,
        decimal_places=3,
    )
    serving_unit = serializers.CharField(source="child_version.serving_unit")
    serving_label = serializers.CharField(source="child_version.serving_label")

    class Meta:
        model = FoodComponent
        fields = (
            "id",
            "food_item_id",
            "food_item_name",
            "food_version_id",
            "servings",
            "order",
            "serving_quantity",
            "serving_unit",
            "serving_label",
        )


class FoodItemVersionSerializer(serializers.ModelSerializer):
    nutrients = serializers.SerializerMethodField()
    sources = SourceReferenceSerializer(many=True, read_only=True)
    components = FoodComponentSerializer(many=True, read_only=True)

    class Meta:
        model = FoodItemVersion
        fields = (
            "id",
            "version_number",
            "serving_quantity",
            "serving_unit",
            "serving_label",
            "provenance",
            "confidence_score",
            "nutrients",
            "sources",
            "components",
            "created_at",
        )

    def get_nutrients(self, instance):
        return [
            {
                "key": key,
                "name": metadata["name"],
                "unit": metadata["unit"],
                "amount": f"{value:.4f}",
            }
            for key, metadata in NUTRIENT_METADATA.items()
            if (value := getattr(instance, key)) is not None
        ]


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


class FoodComponentInputSerializer(serializers.Serializer):
    food_item = serializers.PrimaryKeyRelatedField(queryset=FoodItem.objects.all())
    servings = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    order = serializers.IntegerField(min_value=0, max_value=32767, default=0)

    def validate_food_item(self, food_item):
        request = self.context.get("request")
        if (
            not request
            or not FoodItem.objects.active()
            .visible_to(request.user)
            .filter(pk=food_item.pk)
            .exists()
        ):
            raise serializers.ValidationError("This food is not available.")
        if food_item.current_version_id is None:
            raise serializers.ValidationError("This food has no current definition.")
        return food_item


class FoodDefinitionInputSerializer(serializers.Serializer):
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


def _django_validation_details(error):
    if hasattr(error, "message_dict"):
        return error.message_dict
    return {"detail": error.messages}


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
            "current_version",
            "definition",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scope",
            "current_version",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        definition = attrs.get("definition")
        if self.instance is None and definition is None:
            raise serializers.ValidationError(
                {"definition": "A food definition is required."}
            )
        if self.instance is not None and definition:
            if any(
                item["food_item"].pk == self.instance.pk
                for item in definition.get("components", [])
            ):
                raise serializers.ValidationError(
                    {"definition": {"components": "A food cannot include itself."}}
                )

        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        if not name:
            raise serializers.ValidationError({"name": "This field may not be blank."})
        attrs["name"] = name

        provider_name = attrs.get(
            "provider_name",
            getattr(self.instance, "provider_name", ""),
        ).strip()
        attrs["provider_name"] = provider_name
        origin_type = attrs.get(
            "origin_type",
            getattr(self.instance, "origin_type", FoodItem.OriginType.GENERIC),
        )
        if (
            origin_type
            in {
                FoodItem.OriginType.BRANDED,
                FoodItem.OriginType.RESTAURANT,
            }
            and not provider_name
        ):
            raise serializers.ValidationError(
                {"provider_name": "Branded and restaurant foods require a provider."}
            )
        return attrs

    def create(self, validated_data):
        definition = validated_data.pop("definition")
        request = self.context["request"]
        try:
            return create_food_item(
                scope=FoodItem.Scope.PERSONAL,
                owner=request.user,
                created_by=request.user,
                definition=definition,
                **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _django_validation_details(error)
            ) from error

    def update(self, instance, validated_data):
        definition = validated_data.pop("definition", None)
        request = self.context["request"]
        try:
            with transaction.atomic():
                for field, value in validated_data.items():
                    setattr(instance, field, value)
                instance.full_clean()
                instance.save()
                if definition is not None:
                    create_food_version(
                        food_item=instance,
                        definition=definition,
                        created_by=request.user,
                    )
                return instance
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _django_validation_details(error)
            ) from error
