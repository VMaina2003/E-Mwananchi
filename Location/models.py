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
    
# ============================================================
#   WARD MODEL
# ============================================================
class Ward(models.Model):
    """Represents an electoral ward within a sub-county."""

    subcounty = models.ForeignKey(SubCounty, on_delete=models.CASCADE, related_name="wards")
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("subcounty", "name")
        ordering = ["name"]
        verbose_name_plural = "Wards"

    def __str__(self):
        return f"{self.name} - {self.subcounty.name}, {self.subcounty.county.name}"



# ============================================================
#   LOCATION POINT MODEL
# ============================================================
class LocationPoint(models.Model):
    """Stores an exact GPS location (from citizen reports, etc.)."""

    county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    subcounty = models.ForeignKey(SubCounty, on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address_text = models.CharField(max_length=255, blank=True, help_text="Optional human-readable location")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Location Point"
        verbose_name_plural = "Location Points"
        ordering = ["-created_at"]

    def __str__(self):
        return f"({self.latitude}, {self.longitude}) - {self.address_text or 'Unnamed Location'}"