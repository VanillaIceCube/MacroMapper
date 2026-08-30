from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from foods.models import FoodItem
from foods.nutrients import NUTRIENT_METADATA
from foods.portions import portion_options_for_serving

from .models import MealEntry, MealItem
from .services import _component_tree, replace_meal_items


def _snapshot_has_nutrients(components):
    return all(
        "nutrients" in component
        and _snapshot_has_nutrients(component.get("components", []))
        for component in components
    )


class MealItemSerializer(serializers.ModelSerializer):
    food_item_id = serializers.IntegerField(source="food_version.food_item_id")
    food_version_id = serializers.IntegerField(read_only=True)
    provenance = serializers.CharField(source="food_version.provenance", read_only=True)
    confidence_score = serializers.DecimalField(
        source="food_version.confidence_score",
        max_digits=4,
        decimal_places=3,
        read_only=True,
    )
    nutrients = serializers.SerializerMethodField()
    component_snapshot = serializers.SerializerMethodField()
    portion_options = serializers.SerializerMethodField()

    class Meta:
        model = MealItem
        fields = (
            "id",
            "food_item_id",
            "food_version_id",
            "food_name",
            "provider_name",
            "servings",
            "order",
            "serving_quantity",
            "serving_unit",
            "serving_label",
            "portion_options",
            "provenance",
            "confidence_score",
            "component_snapshot",
            "nutrients",
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

    def get_component_snapshot(self, instance):
        snapshot = instance.component_snapshot
        if _snapshot_has_nutrients(snapshot):
            return snapshot
        return _component_tree(instance.food_version)

    def get_portion_options(self, instance):
        version = instance.food_version
        return portion_options_for_serving(
            quantity=version.serving_quantity,
            unit=version.serving_unit,
            label=version.serving_label,
            weight_grams=version.serving_weight_grams,
            volume_milliliters=version.serving_volume_ml,
        )


class MealItemInputSerializer(serializers.Serializer):
    food_item = serializers.PrimaryKeyRelatedField(queryset=FoodItem.objects.all())
    food_version = serializers.IntegerField(required=False, min_value=1)
    servings = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    order = serializers.IntegerField(min_value=0, max_value=32767)


class MealEntrySerializer(serializers.ModelSerializer):
    confidence_score = serializers.DecimalField(
        source="accepted_proposal.confidence_score",
        max_digits=4,
        decimal_places=3,
        read_only=True,
        allow_null=True,
        default=None,
    )
    items = MealItemSerializer(many=True, read_only=True)
    item_inputs = MealItemInputSerializer(many=True, write_only=True, source="items")

    class Meta:
        model = MealEntry
        fields = (
            "id",
            "entry_date",
            "name",
            "notes",
            "confidence_score",
            "items",
            "item_inputs",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"name": {"allow_blank": True, "required": False}}

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        if not name and self.instance is not None:
            raise serializers.ValidationError({"name": "This field may not be blank."})
        attrs["name"] = name

        item_inputs = attrs.get("items")
        if item_inputs is None:
            if self.instance is None or not self.partial:
                raise serializers.ValidationError(
                    {"item_inputs": "Meal items are required."}
                )
            return attrs
        if not item_inputs:
            raise serializers.ValidationError(
                {"item_inputs": "Add at least one food to the meal."}
            )
        existing_versions = set()
        if self.instance is not None:
            existing_versions = set(
                self.instance.items.values_list(
                    "food_version__food_item_id", "food_version_id"
                )
            )
        request = self.context.get("request")
        available_food_ids = set()
        if request:
            available_food_ids = set(
                FoodItem.objects.active()
                .visible_to(request.user)
                .filter(
                    pk__in=[item["food_item"].pk for item in item_inputs],
                    current_version__isnull=False,
                )
                .values_list("pk", flat=True)
            )
        if any(
            item["food_item"].pk not in available_food_ids
            and (item["food_item"].pk, item.get("food_version"))
            not in existing_versions
            for item in item_inputs
        ):
            raise serializers.ValidationError(
                {"item_inputs": "This food is not available."}
            )
        orders = [item["order"] for item in item_inputs]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                {"item_inputs": "Each meal item order must be unique."}
            )
        supplied_versions = [
            (item["food_item"].pk, item["food_version"])
            for item in item_inputs
            if "food_version" in item
        ]
        if self.instance is None and supplied_versions:
            raise serializers.ValidationError(
                {"item_inputs": "New meals always use each food's current definition."}
            )
        if self.instance is not None:
            if any(pair not in existing_versions for pair in supplied_versions):
                raise serializers.ValidationError(
                    {
                        "item_inputs": "A saved food version must already belong to this meal."
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        item_inputs = validated_data.pop("items")
        meal_entry = MealEntry.objects.create(
            owner=self.context["request"].user,
            **validated_data,
        )
        replace_meal_items(meal_entry=meal_entry, item_inputs=item_inputs)
        return meal_entry

    @transaction.atomic
    def update(self, instance, validated_data):
        item_inputs = validated_data.pop("items", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if item_inputs is not None:
            replace_meal_items(meal_entry=instance, item_inputs=item_inputs)
        return instance
