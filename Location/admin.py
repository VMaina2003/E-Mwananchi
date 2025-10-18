from django.contrib import admin
from .models import County, SubCounty, Ward, LocationPoint


# ============================================================
#   INLINE CLASSES
# ============================================================

class SubCountyInline(admin.TabularInline):
    model = SubCounty
    extra = 0
    fields = ("name", "code")
    show_change_link = True


class WardInline(admin.TabularInline):
    model = Ward
    extra = 0
    fields = ("name", "latitude", "longitude")
    show_change_link = True


# ============================================================
#   COUNTY ADMIN
# ============================================================

@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "capital", "created_at")
    search_fields = ("name", "capital")
    ordering = ("name",)
    inlines = [SubCountyInline]


# ============================================================
#   SUBCOUNTY ADMIN
# ============================================================

@admin.register(SubCounty)
class SubCountyAdmin(admin.ModelAdmin):
    list_display = ("name", "county", "code", "created_at")
    list_filter = ("county",)
    search_fields = ("name", "county__name")
    ordering = ("county__name", "name")
    inlines = [WardInline]


# ============================================================
#   WARD ADMIN
# ============================================================

@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("name", "subcounty", "county_name", "latitude", "longitude")
    list_filter = ("subcounty__county", "subcounty")
    search_fields = ("name", "subcounty__name", "subcounty__county__name")
    ordering = ("subcounty__county__name", "subcounty__name", "name")

    def county_name(self, obj):
        return obj.subcounty.county.name
    county_name.short_description = "County"

# ============================================================
#   LOCATION POINT ADMIN
# ============================================================

@admin.register(LocationPoint)
class LocationPointAdmin(admin.ModelAdmin):
    list_display = ("latitude", "longitude", "county", "subcounty", "ward", "address_text", "created_at")
    list_filter = ("county", "subcounty", "ward")
    search_fields = ("address_text", "county__name", "subcounty__name", "ward__name")
    ordering = ("-created_at",)