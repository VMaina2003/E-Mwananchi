from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    """
    Handles notification creation, listing, marking as read/unread, and deletion.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """a
        Return notifications for the logged-in user.
        """
        user = self.request.user
        return Notification.objects.filter(recipient=user).order_by('-created_at')

    def perform_create(self, serializer):
        """
        Create a notification (e.g., triggered by another event).
        Actor is the current user by default.
        """
        serializer.save(actor=self.request.user)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark all notifications as read for the current user.
        """
        count = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({"message": f"{count} notifications marked as read."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Mark a single notification as read.
        """
        notification = self.get_object()
        if notification.recipient != request.user:
            return Response({"error": "You cannot modify this notification."}, status=status.HTTP_403_FORBIDDEN)

        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)
    