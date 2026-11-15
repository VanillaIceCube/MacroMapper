from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import NotificationSerializer
from .services import (
    clear_all,
    delete_notification,
    mark_all_read,
    notifications_for,
    update_notification,
)


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return notifications_for(self.request.user)

    def perform_update(self, serializer):
        serializer.instance = update_notification(
            self.request.user, serializer.instance, serializer.validated_data
        )

    def perform_destroy(self, instance):
        delete_notification(self.request.user, instance)

    @action(detail=False, methods=["patch"], url_path="mark-all-read")
    def mark_all_read(self, request):
        return Response(
            {"updated": mark_all_read(request.user)}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["delete"], url_path="clear-all")
    def clear_all(self, request):
        return Response({"deleted": clear_all(request.user)}, status=status.HTTP_200_OK)
