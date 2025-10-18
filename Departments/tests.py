from django.db import models
from django.utils import timezone
from django.conf import settings
from Location.models import County


# ============================================================
#   DEPARTMENT MODEL
# ============================================================
class Department(models.Model):
    """Represents a general category of service — e.g. Health, Education, Roads."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.name
