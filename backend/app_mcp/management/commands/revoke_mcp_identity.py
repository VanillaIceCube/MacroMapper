import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app_mcp.auth import ISSUER
from app_mcp.models import IdentityLink, MealConfirmation


class Command(BaseCommand):
    help = "Disable an explicit identity link and remove pending meal confirmations."

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            subject = uuid.UUID(options["subject"])
        except ValueError:
            raise CommandError("Invalid subject.") from None
        links = IdentityLink.objects.filter(issuer=ISSUER, subject=subject)
        MealConfirmation.objects.filter(link__in=links).delete()
        links.update(active=False)
        self.stdout.write("Identity link disabled.")
