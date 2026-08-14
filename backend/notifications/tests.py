from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Notification

User = get_user_model()


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="recipient-password",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="other-password",
        )
        self.notification = Notification.objects.create(
            recipient=self.recipient,
            actor=self.other_user,
            event_type=Notification.EVENT_SYSTEM,
            title="Template ready",
            message="Your application shell is ready.",
            target_path="/",
        )
        self.other_notification = Notification.objects.create(
            recipient=self.other_user,
            title="Private notification",
            message="Only the other user can see this.",
        )

    def test_notification_endpoints_require_authentication(self):
        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_scoped_to_the_authenticated_recipient(self):
        self.client.force_authenticate(user=self.recipient)
        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([item["id"] for item in response.data], [self.notification.id])
        self.assertEqual(response.data[0]["event_type"], Notification.EVENT_SYSTEM)
        self.assertEqual(response.data[0]["target_path"], "/")
        self.assertEqual(response.data[0]["actor_details"]["username"], "other")

    def test_recipient_can_mark_a_notification_read_and_unread(self):
        self.client.force_authenticate(user=self.recipient)

        read_response = self.client.patch(
            f"/api/notifications/{self.notification.id}/",
            {"is_read": True},
            format="json",
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertTrue(read_response.data["is_read"])
        self.assertIsNotNone(read_response.data["read_at"])

        unread_response = self.client.patch(
            f"/api/notifications/{self.notification.id}/",
            {"is_read": False},
            format="json",
        )
        self.assertEqual(unread_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unread_response.data["is_read"])
        self.assertIsNone(unread_response.data["read_at"])

    def test_user_cannot_access_another_users_notification(self):
        self.client.force_authenticate(user=self.recipient)

        retrieve_response = self.client.get(
            f"/api/notifications/{self.other_notification.id}/"
        )
        update_response = self.client.patch(
            f"/api/notifications/{self.other_notification.id}/",
            {"is_read": True},
            format="json",
        )
        delete_response = self.client.delete(
            f"/api/notifications/{self.other_notification.id}/"
        )

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read_only_updates_the_current_users_notifications(self):
        Notification.objects.create(
            recipient=self.recipient,
            title="Second notification",
            message="A second unread notification.",
        )
        self.client.force_authenticate(user=self.recipient)

        response = self.client.patch("/api/notifications/mark-all-read/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.recipient, is_read=False
            ).exists()
        )
        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_clear_all_only_deletes_the_current_users_notifications(self):
        self.client.force_authenticate(user=self.recipient)

        response = self.client.delete("/api/notifications/clear-all/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 1)
        self.assertFalse(Notification.objects.filter(recipient=self.recipient).exists())
        self.assertTrue(
            Notification.objects.filter(pk=self.other_notification.pk).exists()
        )
