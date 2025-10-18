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