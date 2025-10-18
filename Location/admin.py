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
    
