from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CountyViewSet, SubCountyViewSet, WardViewSet, LocationPointViewSet

router = DefaultRouter()
router.register(r'counties', CountyViewSet, basename='county')
router.register(r'subcounties', SubCountyViewSet, basename='subcounty')
router.register(r'wards', WardViewSet, basename='ward')
router.register(r'points', LocationPointViewSet, basename='locationpoint')

urlpatterns = [
    path('', include(router.urls)),
]
