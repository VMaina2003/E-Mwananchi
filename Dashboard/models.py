# Dashboard/models.py
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings

class DashboardMetric(models.Model):
    """
    Stores historical metrics for dashboard analytics and reporting
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    metric_type = models.CharField(
        max_length=50,
        choices=[
            ('daily_reports', 'Daily Reports'),
            ('weekly_activity', 'Weekly Activity'),
            ('monthly_resolution', 'Monthly Resolution Rate'),
            ('user_registrations', 'User Registrations'),
            ('county_breakdown', 'County Breakdown'),
        ]
    )
    
    metric_value = models.JSONField(help_text="Stores metric data in JSON format")
    date_recorded = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['metric_type', 'date_recorded']),
        ]
        ordering = ['-date_recorded']

    def __str__(self):
        return f"{self.metric_type} - {self.date_recorded}"

class SystemAuditLog(models.Model):
    """
    Audit trail for system activities and admin actions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'System Audit Log'
        verbose_name_plural = 'System Audit Logs'

    def __str__(self):
        return f"{self.user.email if self.user else 'System'} - {self.action}"