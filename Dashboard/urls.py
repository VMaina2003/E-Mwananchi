# Dashboard/urls.py
from django.urls import path
from .views import (
    ProfessionalDashboardStatsAPI, 
    RecentActivityAPI,
    CitizenDashboardAPI,
    OfficialDashboardAPI, 
    AdminDashboardAPI
)

urlpatterns = [
    # Main professional dashboard statistics
    path('professional-stats/', ProfessionalDashboardStatsAPI.as_view(), name='professional-dashboard-stats'),
    
    # Recent activity feed
    path('recent-activity/', RecentActivityAPI.as_view(), name='recent-activity'),
    
    # Role-specific dashboard endpoints
    path('citizen/', CitizenDashboardAPI.as_view(), name='citizen-dashboard'),
    path('official/', OfficialDashboardAPI.as_view(), name='official-dashboard'), 
    path('admin/', AdminDashboardAPI.as_view(), name='admin-dashboard'),
]