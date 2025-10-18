from django.contrib import admin
from .models import Report, ReportImage


# ============================================================
#   INLINE IMAGE DISPLAY
# ============================================================
class ReportImageInline(admin.TabularInline):
    """
    Displays related images directly under a report in the admin panel.
    """
    model = ReportImage
    extra = 0
    readonly_fields = ["uploaded_at", "image_preview"]
    fields = ["image", "caption", "uploaded_at", "image_preview"]

    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" width="120" height="80" style="object-fit:cover; border-radius:6px;" />'
        return "(No image)"
    image_preview.allow_tags = True
    image_preview.short_description = "Preview"


# ============================================================
#   REPORT ADMIN CONFIGURATION
# ============================================================
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """
    Admin customization for the Report model.
    Provides filtering, searching, and inline image previews.
    """

    list_display = (
        "title",
        "county",
        "department",
        "status",
        "verified_by_ai",
        "ai_confidence",
        "created_at",
    )

    list_filter = (
        "status",
        "verified_by_ai",
        "county",
        "department",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "county__name",
        "subcounty__name",
        "ward__name",
        "department__department__name",
        "reporter__email",
    )

    readonly_fields = (
        "reporter",
        "role_at_submission",
        "verified_by_ai",
        "ai_confidence",
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
    )

    list_per_page = 20
    ordering = ["-created_at"]
    inlines = [ReportImageInline]

    fieldsets = (
        ("Reporter Information", {
            "fields": ("reporter", "role_at_submission"),
        }),
        ("Issue Details", {
            "fields": ("title", "description", "status", "department"),
        }),
        ("Location", {
            "fields": ("county", "subcounty", "ward", "latitude", "longitude"),
        }),
        ("AI Verification", {
            "fields": ("verified_by_ai", "ai_confidence", "image_required_passed"),
        }),
        ("Timestamps & Audit", {
            "fields": ("created_at", "updated_at", "deleted_at", "deleted_by"),
        }),
    )


# ============================================================
#   REPORT IMAGE ADMIN CONFIGURATION
# ============================================================
@admin.register(ReportImage)
class ReportImageAdmin(admin.ModelAdmin):
    """
    Allows direct management of report images in the admin panel.
    """
    list_display = ("report", "caption", "uploaded_at")
    search_fields = ("report__title", "caption")
    list_filter = ("uploaded_at",)
    ordering = ["-uploaded_at"]
