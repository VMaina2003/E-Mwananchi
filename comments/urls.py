from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CommentViewSet

# Initialize router for automatic route registration
router = DefaultRouter()
router.register(r'comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
]
