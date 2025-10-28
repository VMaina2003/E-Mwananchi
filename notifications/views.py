# from rest_framework import viewsets, permissions, status
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from django.utils import timezone
# from .models import Notification
# from .serializers import NotificationSerializer

# class NotificationViewSet(viewsets.ModelViewSet):
#     """
#     Handles notification creation, listing, marking as read/unread, and deletion.
#     """
#     serializer_class = NotificationSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         """a
#         Return notifications for the logged-in user.
#         """
#         user = self.request.user
#         return Notification.objects.filter(recipient=user).order_by('-created_at')

#     def perform_create(self, serializer):
#         """
#         Create a notification (e.g., triggered by another event).
#         Actor is the current user by default.
#         """
#         serializer.save(actor=self.request.user)

#     @action(detail=False, methods=['post'], url_path='mark-all-read')
#     def mark_all_read(self, request):
#         """
#         Mark all notifications as read for the current user.
#         """
#         count = Notification.objects.filter(recipient=request.user, is_read=False).update(
#             is_read=True,
#             read_at=timezone.now()
#         )
#         return Response({"message": f"{count} notifications marked as read."}, status=status.HTTP_200_OK)

#     @action(detail=True, methods=['post'], url_path='mark-read')
#     def mark_read(self, request, pk=None):
#         """
#         Mark a single notification as read.
#         """
#         notification = self.get_object()
#         if notification.recipient != request.user:
#             return Response({"error": "You cannot modify this notification."}, status=status.HTTP_403_FORBIDDEN)

#         notification.is_read = True
#         notification.read_at = timezone.now()
#         notification.save()
#         return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)

# notifications/views.py (Final Correct Version)

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

# Local Notification imports
from .models import Notification
from .serializers import NotificationSerializer, NotificationUpdateSerializer 
# NOTE: The utils are imported for completeness, although typically called by other apps (like Reports)
from notifications.utils import create_notification, notify_county_officials


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Handles notification listing, marking as read/unread, and deletion for the authenticated user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return notifications for the logged-in user, ordered by creation time (newest first).
        """
        user = self.request.user
        # Filter by recipient (the current user)
        return Notification.objects.filter(recipient=user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark all unread notifications as read for the current user.
        """
        # Bulk update for performance
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
        try:
            notification = self.get_object()
        except Notification.DoesNotExist:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

        if notification.recipient != request.user:
            return Response({"error": "You cannot modify this notification."}, status=status.HTTP_403_FORBIDDEN)

        if not notification.is_read:
            notification.is_read = True
            # Update the read timestamp
            # Assuming you have a read_at field:
            # notification.read_at = timezone.now()
            notification.save(update_fields=["is_read"])
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Allow partial updates for marking as read (e.g. PATCH /notifications/123/ with {'is_read': true})
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if instance.recipient != request.user:
            return Response({"error": "You cannot modify this notification."}, status=status.HTTP_403_FORBIDDEN)

        # Use the NotificationUpdateSerializer for status changes
        serializer = NotificationUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return the fully serialized Notification object
        return Response(NotificationSerializer(instance).data, status=status.HTTP_200_OK)