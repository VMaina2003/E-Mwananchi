from rest_framework import serializers
from .models import County, SubCounty, Ward, LocationPoint


class CountySerializer(serializers.ModelSerializer):
    class Meta:
        model = County
        fields = ['id', 'name', 'code', 'capital', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class SubCountySerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source='county.name', read_only=True)
    
    class Meta:
        model = SubCounty
        fields = ['id', 'name', 'code', 'county', 'county_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class WardSerializer(serializers.ModelSerializer):
    subcounty_name = serializers.CharField(source='subcounty.name', read_only=True)
    county_name = serializers.CharField(source='subcounty.county.name', read_only=True)
    
    class Meta:
        model = Ward
        fields = [
            'id', 'name', 'subcounty', 'subcounty_name', 'county_name', 
            'latitude', 'longitude', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LocationPointSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source='county.name', read_only=True)
    subcounty_name = serializers.CharField(source='subcounty.name', read_only=True)
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    
    class Meta:
        model = LocationPoint
        fields = [
            'id', 'county', 'county_name', 'subcounty', 'subcounty_name', 
            'ward', 'ward_name', 'latitude', 'longitude', 'address_text', 
            'created_at'
        ]
        read_only_fields = ['created_at']