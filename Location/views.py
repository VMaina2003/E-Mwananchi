from rest_framework import viewsets, generics, permissions

from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .models import County, SubCounty, Ward, LocationPoint
from .serializers import (
    CountySerializer,
    SubCountySerializer,
    WardSerializer,
    LocationPointSerializer,
)


# ============================================================
#   COUNTY VIEWSET
# ============================================================
class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides list and detail views for all counties.
    Example:
        GET /api/location/counties/
        GET /api/location/counties/<id>/
    """

    queryset = County.objects.all().order_by("name")
    serializer_class = CountySerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["get"])
    def subcounties(self, request, pk=None):
        """
        Returns all subcounties within a county.
        Example:
            GET /api/location/counties/<id>/subcounties/
        """
        county = self.get_object()
        subcounties = county.subcounties.all().order_by("name")
        serializer = SubCountySerializer(subcounties, many=True)
        return Response(serializer.data)

# ============================================================
#   SUBCOUNTY VIEWSET
# ============================================================
class SubCountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides list and detail views for subcounties.
    Example:
        GET /api/location/subcounties/
        GET /api/location/subcounties/<id>/
    """

    queryset = SubCounty.objects.select_related("county").all().order_by("name")
    serializer_class = SubCountySerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["get"])
    def wards(self, request, pk=None):
        """
        Returns all wards within a subcounty.
        Example:
            GET /api/location/subcounties/<id>/wards/
        """
        subcounty = self.get_object()
        wards = subcounty.wards.all().order_by("name")
        serializer = WardSerializer(wards, many=True)
        return Response(serializer.data)
    
# ============================================================
#   WARD VIEWSET
# ============================================================
class WardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides list and detail views for wards.
    Example:
        GET /api/location/wards/
        GET /api/location/wards/<id>/
    """

    queryset = Ward.objects.select_related("subcounty", "subcounty__county").all().order_by("name")
    serializer_class = WardSerializer
    permission_classes = [permissions.AllowAny]
    

# ============================================================
#   LOCATION POINT VIEWSET
# ============================================================
class LocationPointViewSet(viewsets.ModelViewSet):
    """
    Handles citizen-reported GPS points.
    Example:
        POST /api/location/points/       -> Create a point
        GET  /api/location/points/       -> List points
        GET  /api/location/points/<id>/  -> Retrieve one
    """

    queryset = LocationPoint.objects.select_related("county", "subcounty", "ward").all().order_by("-created_at")
    serializer_class = LocationPointSerializer
    permission_classes = [permissions.AllowAny]  # You can later switch to IsAuthenticated
