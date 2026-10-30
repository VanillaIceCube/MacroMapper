"""An operator must independently verify both existing identities before linking."""

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from app_mcp.auth import ISSUER
from app_mcp.models import IdentityLink


class Command(BaseCommand):
    help = "Explicitly link an issuer UUID to an existing active local user ID; never overwrite."

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True)
        parser.add_argument("--user-id", required=True, type=int)

    def handle(self, *args, **options):
        try:
            subject = uuid.UUID(options["subject"])
            user = get_user_model().objects.get(pk=options["user_id"], is_active=True)
            with transaction.atomic():
                IdentityLink.objects.create(issuer=ISSUER, subject=subject, user=user)
        except (ValueError, get_user_model().DoesNotExist, IntegrityError):
            raise CommandError(
                "Identity link refused; verify identities and existing links privately."
            ) from None
        self.stdout.write("Identity link created.")
