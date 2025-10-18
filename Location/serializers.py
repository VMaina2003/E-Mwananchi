from rest_framework import serializers
from .models import County, SubCounty, Ward, LocationPoint


# ============================================================
#   COUNTY SERIALIZER
# ============================================================
class CountySerializer(serializers.ModelSerializer):
    class Meta:
        model = County
        fields = ["id", "name", "code", "capital"]
