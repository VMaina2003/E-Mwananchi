from django.contrib import admin
from .models import Department, CountyDepartment, DepartmentOfficial


# ============================================================
#   INLINE CLASSES
# ============================================================

class CountyDepartmentInline(admin.TabularInline):
    """Inline to view county departments under a main department."""
    model = CountyDepartment
    extra = 0
    fields = ("county", "email", "phone_number", "office_location", "is_active")
    show_change_link = True


class DepartmentOfficialInline(admin.TabularInline):
    """Inline to view officials within a county department."""
    model = DepartmentOfficial
    extra = 0
    fields = ("user", "position", "is_head")
    show_change_link = True



# ============================================================
#   DEPARTMENT ADMIN
# ============================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [CountyDepartmentInline]
    

# ============================================================
#   COUNTY DEPARTMENT ADMIN
# ============================================================

@admin.register(CountyDepartment)
class CountyDepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "department",
        "county",
        "email",
        "phone_number",
        "office_location",
        "is_active",
        "created_at",
    )
    list_filter = ("county", "department", "is_active")
    search_fields = (
        "department__name",
        "county__name",
        "email",
        "phone_number",
        "office_location",
    )
    ordering = ("county__name", "department__name")
    inlines = [DepartmentOfficialInline]


# ============================================================
#   DEPARTMENT OFFICIAL ADMIN
# ============================================================

@admin.register(DepartmentOfficial)
class DepartmentOfficialAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "county_department",
        "get_county",
        "get_department",
        "position",
        "is_head",
    )
    list_filter = ("is_head", "county_department__county", "county_department__department")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "county_department__county__name",
        "county_department__department__name",
    )
    ordering = ("county_department__county__name", "county_department__department__name")

    def get_county(self, obj):
        return obj.county_department.county.name
    get_county.short_description = "County"

    def get_department(self, obj):
        return obj.county_department.department.name
    get_department.short_description = "Department"