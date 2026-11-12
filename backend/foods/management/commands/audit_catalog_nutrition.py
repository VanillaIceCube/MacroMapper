"""Read-only by default; quarantine only explicitly selected, still-empty foods."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from foods.evidence import usable_nutrition
from foods.models import FoodItem
from foods.nutrients import NUTRIENT_FIELDS
from foods.services import build_component_map
from meals.services import _effective_nutrients


class Command(BaseCommand):
    help = "Report unusable active shared foods; optionally archive reviewed IDs, preserving all history."

    def add_arguments(self, parser):
        parser.add_argument("--archive", action="store_true")
        parser.add_argument("--food-id", action="append", type=int, default=[])

    @transaction.atomic
    def handle(self, *args, **options):
        selected = set(options["food_id"])
        if options["archive"] and not selected:
            raise CommandError("Archiving requires explicit reviewed --food-id values.")
        foods = FoodItem.objects.active().filter(scope=FoodItem.Scope.SHARED)
        if selected:
            foods = foods.filter(pk__in=selected)
        if options["archive"]:
            foods = foods.select_for_update()
        foods = list(foods.select_related("current_version"))
        component_map = build_component_map([food.current_version_id for food in foods])
        affected = [
            food
            for food in foods
            if food.current_version is None
            or (
                not usable_nutrition(
                    {
                        field: getattr(food.current_version, field)
                        for field in NUTRIENT_FIELDS
                    }
                )
                and not usable_nutrition(
                    _effective_nutrients(
                        food.current_version, component_map=component_map
                    )
                )
            )
        ]
        if options["archive"] and selected != {food.pk for food in affected}:
            raise CommandError(
                "Selection changed or includes usable, personal, missing or archived foods; rerun the audit."
            )
        report = [
            {"food_id": food.pk, "version_id": food.current_version_id}
            for food in affected
        ]
        if options["archive"]:
            FoodItem.objects.filter(pk__in=selected).update(archived_at=timezone.now())
        self.stdout.write(
            json.dumps(
                {
                    "action": "archived" if options["archive"] else "dry_run",
                    "foods": report,
                }
            )
        )
