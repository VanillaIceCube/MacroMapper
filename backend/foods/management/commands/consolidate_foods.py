from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from foods.services import consolidate_shared_foods


class Command(BaseCommand):
    help = "Review an explicit duplicate shared-food set. Defaults to dry run; --apply archives aliases while preserving historical references."

    def add_arguments(self, parser):
        parser.add_argument("food_ids", type=int, nargs="+")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            canonical = consolidate_shared_foods(
                options["food_ids"], apply=options["apply"]
            )
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        action = "Consolidated" if options["apply"] else "Dry run: would consolidate"
        self.stdout.write(
            f"{action} {options['food_ids']} under canonical food {canonical.pk}; historical snapshots are preserved."
        )
