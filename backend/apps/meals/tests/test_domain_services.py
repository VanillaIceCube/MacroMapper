"""Direct diary services preserve ownership and catalog authorization."""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .. import services
from ..models import MealEntry
from .helpers import MealEntryFixtures


class MealDomainServiceTests(MealEntryFixtures, TestCase):
    def inputs(self, food):
        return {
            "entry_date": date(2026, 11, 15),
            "name": "Lunch",
            "items": [{"food_item": food, "servings": Decimal("1"), "order": 0}],
        }

    def test_direct_create_rejects_foreign_private_food_without_writes(self):
        with self.assertRaises(ValidationError):
            services.create_meal(self.owner, self.inputs(self.other_food))
        self.assertFalse(MealEntry.objects.exists())

    def test_direct_update_and_delete_require_current_owner(self):
        meal = services.create_meal(self.owner, self.inputs(self.apple))
        self.assertEqual(meal.items.get().food_name, "Apple")
        for operation, args in (
            (services.update_meal, ({"name": "Foreign"},)),
            (services.delete_meal, ()),
        ):
            with self.assertRaises(PermissionDenied):
                operation(self.other_user, meal, *args)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Lunch")
        self.assertEqual(meal.items.count(), 1)


class DomainServiceDependencyTests(SimpleTestCase):
    def test_domain_service_imports_are_acyclic_including_lazy_imports(self):
        apps = Path(services.__file__).resolve().parents[1]
        graph = {}
        for source in apps.glob("*/services.py"):
            module = f"apps.{source.parent.name}.services"
            dependencies = set()
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module:
                    dependencies.add(node.module)
                    dependencies.update(
                        f"{node.module}.{name.name}" for name in node.names
                    )
                elif isinstance(node, ast.Import):
                    dependencies.update(name.name for name in node.names)
            graph[module] = dependencies

        def visit(module, ancestors):
            self.assertNotIn(
                module, ancestors, f"Cyclic services: {ancestors} -> {module}"
            )
            for dependency in graph[module] & graph.keys():
                visit(dependency, (*ancestors, module))

        for module in graph:
            visit(module, ())
