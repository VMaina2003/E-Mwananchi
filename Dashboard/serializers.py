# Dashboard/serializers.py
from rest_framework import serializers

class DashboardStatsSerializer(serializers.Serializer):
    total_reports = serializers.IntegerField()
    verified_reports = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
    resolved_reports = serializers.IntegerField()
    recent_reports_count = serializers.IntegerField()
    reports_by_status = serializers.DictField()
    reports_by_county = serializers.DictField()
    reports_by_department = serializers.DictField()

class RecentActivitySerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.CharField()
    user = serializers.DictField()
    target = serializers.DictField()
    timestamp = serializers.DateTimeField()
    metadata = serializers.DictField()