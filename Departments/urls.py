from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    CountyDepartmentViewSet,
    DepartmentOfficialViewSet,
)

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"county-departments", CountyDepartmentViewSet, basename="county-departments")
router.register(r"department-officials", DepartmentOfficialViewSet, basename="department-officials")

urlpatterns = router.urls
