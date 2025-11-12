from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CountyViewSet, SubCountyViewSet, WardViewSet, LocationPointViewSet, reverse_geocode

router = DefaultRouter()
router.register(r'counties', CountyViewSet)
router.register(r'subcounties', SubCountyViewSet)
router.register(r'wards', WardViewSet)
router.register(r'location-points', LocationPointViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reverse-geocode/', reverse_geocode, name='reverse-geocode'),
]