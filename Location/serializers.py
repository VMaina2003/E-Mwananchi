from rest_framework import serializers
from .models import County, SubCounty, Ward, LocationPoint


# ============================================================
#   COUNTY SERIALIZER
# ============================================================
class CountySerializer(serializers.ModelSerializer):
    class Meta:
        model = County
        fields = ["id", "name", "code", "capital"]

# ============================================================
#   SUBCOUNTY SERIALIZER
# ============================================================
class SubCountySerializer(serializers.ModelSerializer):
    county = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SubCounty
        fields = ["id", "name", "code", "county"]
        

# ============================================================
#   WARD SERIALIZER
# ============================================================
class WardSerializer(serializers.ModelSerializer):
    subcounty = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Ward
        fields = ["id", "name", "latitude", "longitude", "subcounty"]