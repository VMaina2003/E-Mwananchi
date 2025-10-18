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
    
    
# ============================================================
#    COUNTY DEPARTMENT MODEL
# ============================================================
class CountyDepartment(models.Model):
    """Represents a specific department office within a county."""

    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name="county_departments")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="county_departments")
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    office_location = models.CharField(max_length=255, blank=True, null=True, help_text="Physical office address")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("county", "department")
        ordering = ["county__name", "department__name"]
        verbose_name = "County Department"
        verbose_name_plural = "County Departments"

    def __str__(self):
        return f"{self.department.name} - {self.county.name}"
