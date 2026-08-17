from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from foods.models import FoodItem
from foods.nutrients import NUTRIENT_METADATA

from .models import MealEntry, MealItem
from .services import replace_meal_items


class MealItemSerializer(serializers.ModelSerializer):
    food_item_id = serializers.IntegerField(source="food_version.food_item_id")
    food_version_id = serializers.IntegerField(read_only=True)
    nutrients = serializers.SerializerMethodField()

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
    items = MealItemSerializer(many=True, read_only=True)
    item_inputs = MealItemInputSerializer(many=True, write_only=True, source="items")

    class Meta:
        model = MealEntry
        fields = (
            "id",
            "entry_date",
            "name",
            "notes",
            "items",
            "item_inputs",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        if not name:
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
