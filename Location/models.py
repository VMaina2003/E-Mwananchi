from django.db import models
from django.utils import timezone


# ============================================================
#   COUNTY MODEL
# ============================================================
class County(models.Model):
    """Represents one of Kenya’s 47 counties."""

    name = models.CharField(max_length=100, unique=True)
    code = models.PositiveIntegerField(unique=True, help_text="Official county code")
    capital = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Counties"

    def __str__(self):
        return f"{self.name} County"
    
# ============================================================
#   SUBCOUNTY MODEL
# ============================================================
class SubCounty(models.Model):
    """Represents a sub-county (constituency) within a county."""

    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name="subcounties")
    name = models.CharField(max_length=100)
    code = models.PositiveIntegerField(blank=True, null=True, help_text="Optional subcounty code")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("county", "name")
        ordering = ["name"]
        verbose_name_plural = "Subcounties"

    def __str__(self):
        return f"{self.name} ({self.county.name})"
