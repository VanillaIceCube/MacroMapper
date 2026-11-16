"""Recipient and preview-selected boundaries apply to direct notification calls."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .. import services
from ..models import Notification


class NotificationDomainServiceTests(TestCase):
    def test_foreign_and_new_notifications_are_excluded_from_selected_bulk_action(self):
        actor = get_user_model().objects.create_user(
            "domain-recipient", email="recipient@example.test"
        )
        other = get_user_model().objects.create_user(
            "other-recipient", email="other@example.test"
        )
        selected = Notification.objects.create(recipient=actor, title="Selected")
        later = Notification.objects.create(recipient=actor, title="Later")
        foreign = Notification.objects.create(recipient=other, title="Foreign")
        self.assertEqual(services.mark_all_read(actor, [selected.pk, foreign.pk]), 1)
        selected.refresh_from_db()
        self.assertTrue(selected.is_read)
        self.assertIsNotNone(selected.read_at)
        with self.assertRaises(PermissionDenied):
            services.update_notification(actor, foreign, {"is_read": True})
        self.assertEqual(services.clear_all(actor, [selected.pk, foreign.pk]), 1)
        self.assertEqual(
            set(Notification.objects.values_list("pk", flat=True)),
            {later.pk, foreign.pk},
        )
