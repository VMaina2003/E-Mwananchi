from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
import math

from .models import County, SubCounty, Ward, LocationPoint
from .serializers import CountySerializer, SubCountySerializer, WardSerializer, LocationPointSerializer


# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================
class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow only Admin or SuperAdmin to create, update, or delete.
    Others can only read.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (request.user.is_admin or request.user.is_superadmin)


# ============================================================
#   COUNTY VIEWSET
# ============================================================
class CountyViewSet(viewsets.ModelViewSet):
    """
    Manage counties - read-only for most users, admin can modify.
    """
    queryset = County.objects.all().order_by('name')
    serializer_class = CountySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'code']

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def search(self, request):
        """
        Search counties by name
        """
        query = request.query_params.get('q', '')
        if query:
            counties = County.objects.filter(
                Q(name__icontains=query) | 
                Q(code__icontains=query)
            ).order_by('name')
            serializer = self.get_serializer(counties, many=True)
            return Response(serializer.data)
        return Response([])


# ============================================================
#   SUBCOUNTY VIEWSET
# ============================================================
class SubCountyViewSet(viewsets.ModelViewSet):
    """
    Manage subcounties - read-only for most users, admin can modify.
    """
    queryset = SubCounty.objects.all().select_related('county').order_by('name')
    serializer_class = SubCountySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['county', 'name']

    def get_queryset(self):
        queryset = super().get_queryset()
        county_id = self.request.query_params.get('county')
        if county_id:
            queryset = queryset.filter(county_id=county_id)
        return queryset

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def by_county(self, request):
        """
        Get all subcounties for a specific county
        """
        county_id = request.query_params.get('county')
        if not county_id:
            return Response(
                {"error": "County ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        subcounties = SubCounty.objects.filter(county_id=county_id).order_by('name')
        serializer = self.get_serializer(subcounties, many=True)
        return Response(serializer.data)


# ============================================================
#   WARD VIEWSET
# ============================================================
class WardViewSet(viewsets.ModelViewSet):
    """
    Manage wards - read-only for most users, admin can modify.
    """
    queryset = Ward.objects.all().select_related('subcounty', 'subcounty__county').order_by('name')
    serializer_class = WardSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['subcounty', 'name']

    def get_queryset(self):
        queryset = super().get_queryset()
        subcounty_id = self.request.query_params.get('subcounty')
        if subcounty_id:
            queryset = queryset.filter(subcounty_id=subcounty_id)
        return queryset

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def by_subcounty(self, request):
        """
        Get all wards for a specific subcounty
        """
        subcounty_id = request.query_params.get('subcounty')
        if not subcounty_id:
            return Response(
                {"error": "Subcounty ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        wards = Ward.objects.filter(subcounty_id=subcounty_id).order_by('name')
        serializer = self.get_serializer(wards, many=True)
        return Response(serializer.data)


# ============================================================
#   LOCATION POINT VIEWSET
# ============================================================
class LocationPointViewSet(viewsets.ModelViewSet):
    """
    Manage location points for precise GPS locations.
    """
    queryset = LocationPoint.objects.all().select_related('county', 'subcounty', 'ward')
    serializer_class = LocationPointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ============================================================
#   REVERSE GEOCODING ENDPOINT
# ============================================================
@api_view(['POST'])
def reverse_geocode(request):
    """
    Reverse geocode coordinates to Kenyan administrative areas
    """
    try:
        lat = float(request.data.get('latitude'))
        lng = float(request.data.get('longitude'))
    except (TypeError, ValueError):
        return Response({'error': 'Invalid coordinates'}, status=400)

    # Find the closest ward using distance calculation
    closest_ward = find_closest_ward(lat, lng)
    
    if closest_ward:
        return Response({
            'county': {
                'id': closest_ward.subcounty.county.id,
                'name': closest_ward.subcounty.county.name
            },
            'subcounty': {
                'id': closest_ward.subcounty.id,
                'name': closest_ward.subcounty.name
            },
            'ward': {
                'id': closest_ward.id,
                'name': closest_ward.name
            },
            'confidence': 'high'
        })
    
    # Fallback: Find closest county if no ward found
    closest_county = find_closest_county(lat, lng)
    if closest_county:
        return Response({
            'county': {
                'id': closest_county.id,
                'name': closest_county.name
            },
            'subcounty': None,
            'ward': None,
            'confidence': 'medium'
        })
    
    return Response({'error': 'Location not found in Kenyan database'}, status=404)


def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lng/2) * math.sin(delta_lng/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def find_closest_ward(lat, lng):
    """Find the closest ward to the given coordinates"""
    closest_ward = None
    min_distance = float('inf')
    
    # Get all wards with coordinates
    wards = Ward.objects.filter(
        latitude__isnull=False, 
        longitude__isnull=False
    ).select_related('subcounty', 'subcounty__county')
    
    for ward in wards:
        try:
            distance = calculate_distance(lat, lng, float(ward.latitude), float(ward.longitude))
            if distance < min_distance and distance < 50:  # Within 50km
                min_distance = distance
                closest_ward = ward
        except (TypeError, ValueError):
            continue
    
    return closest_ward


def find_closest_county(lat, lng):
    """Find the closest county using accurate county center coordinates"""
    counties = County.objects.all()
    
    # Accurate county center coordinates for all 47 Kenyan counties
    county_centers = {
        # Coastal Region
        'Mombasa': (-4.0435, 39.6682),
        'Kwale': (-4.1737, 39.4521),
        'Kilifi': (-3.5107, 39.9093),
        'Tana River': (-1.5000, 40.0000),
        'Lamu': (-2.2696, 40.9000),
        'Taita-Taveta': (-3.3969, 38.5560),
        
        # North Eastern Region
        'Garissa': (-0.4566, 39.6460),
        'Wajir': (1.7500, 40.0500),
        'Mandera': (3.9369, 41.8670),
        
        # Eastern Region
        'Marsabit': (2.3340, 37.9900),
        'Isiolo': (0.3556, 37.5833),
        'Meru': (0.0500, 37.6500),
        'Tharaka-Nithi': (-0.3000, 37.8333),
        'Embu': (-0.5390, 37.4574),
        'Kitui': (-1.3670, 38.0106),
        'Machakos': (-1.5177, 37.2634),
        'Makueni': (-2.2000, 37.7333),
        
        # Central Region
        'Nyandarua': (-0.4167, 36.6667),
        'Nyeri': (-0.4167, 36.9500),
        'Kirinyaga': (-0.5000, 37.2833),
        "Murang'a": (-0.7833, 37.0333),
        'Kiambu': (-1.1667, 36.8333),
        
        # Rift Valley Region
        'Turkana': (3.1167, 35.6000),
        'West Pokot': (1.5000, 35.2833),
        'Samburu': (1.1000, 36.7000),
        'Trans Nzoia': (1.0333, 34.9667),
        'Uasin Gishu': (0.5143, 35.2698),  # Eldoret
        'Elgeyo-Marakwet': (0.5000, 35.6500),
        'Nandi': (0.2000, 35.1000),
        'Baringo': (0.4667, 35.9667),
        'Laikipia': (0.2500, 36.7500),
        'Nakuru': (-0.3031, 36.0800),
        'Narok': (-1.0833, 35.8667),
        'Kajiado': (-1.8500, 36.7833),
        'Kericho': (-0.3667, 35.2833),
        'Bomet': (-0.7833, 35.3333),
        'Kakamega': (0.2833, 34.7500),
        
        # Western Region
        'Vihiga': (0.0833, 34.7167),
        'Bungoma': (0.5667, 34.5667),
        'Busia': (0.4667, 34.1167),
        'Siaya': (0.0667, 34.2833),
        'Kisumu': (-0.1022, 34.7617),
        'Homa Bay': (-0.5167, 34.4500),
        'Migori': (-1.0667, 34.4667),
        'Kisii': (-0.6833, 34.7667),
        'Nyamira': (-0.5667, 34.9667),
        
        # Nairobi
        'Nairobi': (-1.286389, 36.817223),
    }
    
    closest_county = None
    min_distance = float('inf')
    
    for county in counties:
        if county.name in county_centers:
            county_lat, county_lng = county_centers[county.name]
            distance = calculate_distance(lat, lng, county_lat, county_lng)
            if distance < min_distance:
                min_distance = distance
                closest_county = county
    
    return closest_county or counties.first()