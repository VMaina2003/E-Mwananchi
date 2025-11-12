# Dashboard/views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Count, Q, Avg, Max, Min, Sum
from django.utils import timezone
from datetime import timedelta, datetime
from django.db import connection
from collections import defaultdict

from Reports.models import Report, GovernmentDevelopment
from Departments.models import CountyDepartment, DepartmentOfficial
from Authentication.models import CustomUser
from Location.models import County
from comments.models import Comment
from notifications.models import Notification

logger = logging.getLogger(__name__)

class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """Enhanced permission class with professional role management"""
    allowed_roles = [
        CustomUser.Roles.CITIZEN,
        CustomUser.Roles.COUNTY_OFFICIAL,
        CustomUser.Roles.ADMIN,
        CustomUser.Roles.SUPERADMIN,
        CustomUser.Roles.VIEWER,
    ]

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in self.allowed_roles
        )

class ProfessionalDashboardStatsAPI(APIView):
    """
    Professional dashboard statistics with comprehensive analytics
    """
    permission_classes = [IsAuthenticatedAndHasRole]

    def get(self, request):
        try:
            user = request.user
            logger.info(f"Fetching professional dashboard stats for user: {user.email}, role: {user.role}")

            # Role-based professional statistics
            if user.is_superadmin:
                stats = self._get_superadmin_stats()
            elif user.is_admin:
                stats = self._get_admin_stats()
            elif user.is_county_official:
                stats = self._get_official_stats(user)
            else:
                stats = self._get_citizen_stats(user)

            return Response(stats, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Professional dashboard stats error: {str(e)}")
            return Response(
                {"error": "Failed to fetch dashboard statistics"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_superadmin_stats(self):
        """Comprehensive system-wide statistics for superadmin"""
        # Basic counts with performance metrics
        total_reports = Report.objects.count()
        total_users = CustomUser.objects.count()
        total_departments = CountyDepartment.objects.count()
        
        # Time-based analytics
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        recent_reports = Report.objects.filter(created_at__gte=week_ago)
        recent_users = CustomUser.objects.filter(created_at__gte=week_ago)
        
        stats = {
            # System Overview
            'system_overview': {
                'total_reports': total_reports,
                'total_users': total_users,
                'total_departments': total_departments,
                'total_counties': County.objects.count(),
                'active_sessions': self._get_active_sessions_count(),
            },
            
            # Performance Metrics
            'performance_metrics': {
                'system_uptime': self._calculate_system_uptime(),
                'response_time_avg': self._get_avg_response_time(),
                'resolution_rate': self._get_system_resolution_rate(),
                'user_satisfaction': self._get_user_satisfaction_score(),
            },
            
            # Time-based Analytics
            'time_analytics': {
                'reports_this_week': recent_reports.count(),
                'reports_this_month': Report.objects.filter(created_at__gte=month_ago).count(),
                'new_users_this_week': recent_users.count(),
                'reports_growth_rate': self._calculate_growth_rate(Report.objects, 'created_at', week_ago),
                'users_growth_rate': self._calculate_growth_rate(CustomUser.objects, 'created_at', week_ago),
            },
            
            # Geographic Distribution
            'geographic_distribution': self._get_geographic_distribution(),
            
            # Department Performance
            'department_performance': self._get_department_performance(),
            
            # User Analytics
            'user_analytics': {
                'users_by_role': dict(
                    CustomUser.objects
                    .values('role')
                    .annotate(count=Count('id'))
                    .values_list('role', 'count')
                ),
                'active_users': CustomUser.objects.filter(is_active=True).count(),
                'verified_users': CustomUser.objects.filter(verified=True).count(),
                'user_engagement_rate': self._calculate_user_engagement_rate(),
            },
            
            # AI Performance
            'ai_performance': {
                'ai_verified_reports': Report.objects.filter(verified_by_ai=True).count(),
                'avg_ai_confidence': Report.objects.filter(verified_by_ai=True).aggregate(avg=Avg('ai_confidence'))['avg'] or 0,
                'ai_accuracy_rate': self._calculate_ai_accuracy_rate(),
            },
            
            # Financial Metrics (if applicable)
            'financial_metrics': {
                'development_budgets': self._get_development_budgets_summary(),
                'cost_savings': self._estimate_cost_savings(),
            }
        }
        
        return stats

    def _get_admin_stats(self):
        """Administrator statistics with multi-county oversight"""
        # Admin can see all counties but with administrative focus
        total_reports = Report.objects.count()
        recent_reports = Report.objects.filter(created_at__gte=timezone.now() - timedelta(days=7))
        
        stats = {
            # Administrative Overview
            'admin_overview': {
                'total_reports': total_reports,
                'total_users': CustomUser.objects.count(),
                'total_counties': County.objects.count(),
                'active_departments': CountyDepartment.objects.filter(is_active=True).count(),
            },
            
            # Content Management
            'content_management': {
                'pending_moderation': Report.objects.filter(status='submitted').count(),
                'recent_comments': Comment.objects.filter(created_at__gte=timezone.now() - timedelta(days=7)).count(),
                'reported_content': 0,  # Would integrate with reporting system
                'content_quality_score': self._calculate_content_quality_score(),
            },
            
            # County Performance
            'county_performance': self._get_county_performance_metrics(),
            
            # User Management
            'user_management': {
                'users_awaiting_approval': CustomUser.objects.filter(is_active=False).count(),
                'recent_registrations': CustomUser.objects.filter(created_at__gte=timezone.now() - timedelta(days=7)).count(),
                'user_activity_rate': self._calculate_user_activity_rate(),
            },
            
            # System Health
            'system_health': {
                'avg_response_time': self._get_avg_response_time(),
                'error_rate': self._get_system_error_rate(),
                'uptime': self._calculate_system_uptime(),
            }
        }
        
        return stats

    def _get_official_stats(self, user):
        """Professional statistics for county officials with cross-county visibility"""
        # County officials can see all counties but only manage their assigned county
        all_counties_data = self._get_all_counties_overview()
        assigned_county_data = self._get_county_detailed_stats(user.county) if user.county else {}
        
        stats = {
            # National Overview (Read-only)
            'national_overview': all_counties_data,
            
            # Assigned County Management
            'assigned_county': assigned_county_data,
            
            # Performance Metrics
            'performance_metrics': {
                'county_rank': self._get_county_ranking(user.county) if user.county else None,
                'response_efficiency': self._get_county_response_efficiency(user.county) if user.county else None,
                'citizen_satisfaction': self._get_county_satisfaction_score(user.county) if user.county else None,
            },
            
            # Department Coordination
            'department_coordination': self._get_county_department_coordination(user.county) if user.county else {},
            
            # Recent Activity
            'recent_activity': {
                'new_reports_today': Report.objects.filter(
                    county=user.county,
                    created_at__date=timezone.now().date()
                ).count() if user.county else 0,
                'pending_actions': Report.objects.filter(
                    county=user.county,
                    status__in=['verified', 'noted']
                ).count() if user.county else 0,
                'recent_resolutions': Report.objects.filter(
                    county=user.county,
                    status='resolved',
                    updated_at__gte=timezone.now() - timedelta(days=7)
                ).count() if user.county else 0,
            }
        }
        
        return stats

    def _get_citizen_stats(self, user):
        """Enhanced citizen statistics with personal and community insights"""
        user_reports = Report.objects.filter(reporter=user)
        user_county_reports = Report.objects.filter(county=user.county) if user.county else Report.objects.none()
        
        stats = {
            # Personal Analytics
            'personal_analytics': {
                'my_total_reports': user_reports.count(),
                'my_resolved_reports': user_reports.filter(status='resolved').count(),
                'my_pending_reports': user_reports.filter(status__in=['submitted', 'verified', 'pending']).count(),
                'my_engagement_score': self._calculate_personal_engagement_score(user),
                'report_success_rate': self._calculate_personal_success_rate(user),
            },
            
            # Community Insights
            'community_insights': {
                'county_total_reports': user_county_reports.count() if user.county else 0,
                'county_resolved_reports': user_county_reports.filter(status='resolved').count() if user.county else 0,
                'county_active_issues': user_county_reports.filter(status__in=['verified', 'pending', 'noted', 'on_progress']).count() if user.county else 0,
                'top_departments': self._get_county_top_departments(user.county) if user.county else [],
            },
            
            # Activity Tracking
            'activity_tracking': {
                'my_recent_comments': Comment.objects.filter(
                    user=user,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
                'my_recent_likes': user.liked_reports.count(),
                'my_notifications': Notification.objects.filter(recipient=user, is_read=False).count(),
            },
            
            # Impact Metrics
            'impact_metrics': {
                'community_contribution_score': self._calculate_community_contribution(user),
                'influence_rating': self._calculate_influence_rating(user),
                'response_rate_to_my_reports': self._get_response_rate_to_user_reports(user),
            }
        }
        
        return stats

    # ============ MISSING METHOD IMPLEMENTATIONS ============

    def _get_active_sessions_count(self):
        """Get approximate active sessions count"""
        try:
            from django.contrib.sessions.models import Session
            return Session.objects.filter(expire_date__gt=timezone.now()).count()
        except:
            return 0

    def _calculate_system_uptime(self):
        """Calculate system uptime percentage"""
        # This would integrate with monitoring system
        return 99.95  # Placeholder

    def _get_avg_response_time(self):
        """Calculate average official response time"""
        try:
            responded_reports = Report.objects.filter(
                response_date__isnull=False,
                created_at__isnull=False
            )
            if responded_reports.exists():
                total_hours = sum(
                    (report.response_date - report.created_at).total_seconds() / 3600
                    for report in responded_reports
                )
                return round(total_hours / responded_reports.count(), 2)
        except:
            pass
        return 0

    def _get_system_resolution_rate(self):
        """Calculate system-wide resolution rate"""
        total_resolved = Report.objects.filter(status='resolved').count()
        total_closed = Report.objects.filter(status__in=['resolved', 'rejected']).count()
        return round((total_resolved / total_closed * 100), 2) if total_closed > 0 else 0

    def _get_user_satisfaction_score(self):
        """Calculate user satisfaction score"""
        return 4.5  # Placeholder - would integrate with feedback system

    def _calculate_growth_rate(self, queryset, date_field, since_date):
        """Calculate growth rate for any model"""
        current_count = queryset.filter(**{f"{date_field}__gte": since_date}).count()
        previous_count = queryset.filter(
            **{f"{date_field}__gte": since_date - timedelta(days=7),
               f"{date_field}__lt": since_date}
        ).count()
        
        if previous_count == 0:
            return current_count * 100  # Infinite growth from zero
        return round(((current_count - previous_count) / previous_count) * 100, 2)

    def _get_geographic_distribution(self):
        """Get detailed geographic distribution"""
        counties = County.objects.annotate(
            report_count=Count('reports'),
            resolved_count=Count('reports', filter=Q(reports__status='resolved')),
            user_count=Count('users')
        ).values('id', 'name', 'report_count', 'resolved_count', 'user_count')
        
        return list(counties)

    def _get_department_performance(self):
        """Get department performance metrics"""
        departments = CountyDepartment.objects.annotate(
            total_reports=Count('reports'),
            resolved_reports=Count('reports', filter=Q(reports__status='resolved'))
        ).values('id', 'department__name', 'county__name', 'total_reports', 'resolved_reports')
        
        return list(departments)

    def _calculate_user_engagement_rate(self):
        """Calculate overall user engagement rate"""
        active_users = CustomUser.objects.filter(
            Q(reports__isnull=False) | 
            Q(comments__isnull=False) |
            Q(liked_reports__isnull=False)
        ).distinct().count()
        total_users = CustomUser.objects.count()
        
        return round((active_users / total_users * 100), 2) if total_users > 0 else 0

    def _calculate_ai_accuracy_rate(self):
        """Calculate AI classification accuracy rate"""
        return 87.5  # Placeholder - would integrate with AI accuracy tracking

    def _get_development_budgets_summary(self):
        """Get development budgets summary"""
        developments = GovernmentDevelopment.objects.aggregate(
            total_budget=Sum('budget'),
            avg_budget=Avg('budget'),
            active_projects=Count('id', filter=Q(status='in_progress'))
        )
        return developments

    def _estimate_cost_savings(self):
        """Estimate cost savings from digital platform"""
        reports_resolved = Report.objects.filter(status='resolved').count()
        estimated_savings = reports_resolved * 5000  # KES 5000 per report saved
        return estimated_savings

    def _calculate_content_quality_score(self):
        """Calculate content quality score"""
        return 8.7  # Placeholder

    def _get_county_performance_metrics(self):
        """Get county performance metrics"""
        counties = County.objects.annotate(
            total_reports=Count('reports'),
            resolved_reports=Count('reports', filter=Q(reports__status='resolved')),
            resolution_rate=Count('reports', filter=Q(reports__status='resolved')) * 100.0 / Count('reports')
        ).values('id', 'name', 'total_reports', 'resolved_reports', 'resolution_rate')
        return list(counties)

    def _calculate_user_activity_rate(self):
        """Calculate user activity rate"""
        active_users = CustomUser.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=30)
        ).count()
        total_users = CustomUser.objects.count()
        return round((active_users / total_users * 100), 2) if total_users > 0 else 0

    def _get_system_error_rate(self):
        """Get system error rate"""
        return 0.2  # Placeholder

    def _get_all_counties_overview(self):
        """Get overview of all counties for officials"""
        counties = County.objects.annotate(
            total_reports=Count('reports'),
            resolved_reports=Count('reports', filter=Q(reports__status='resolved')),
            active_officials=Count('users', filter=Q(users__role='county_official', users__is_active=True))
        ).values('id', 'name', 'total_reports', 'resolved_reports', 'active_officials')
        
        return list(counties)

    def _get_county_detailed_stats(self, county):
        """Get detailed statistics for specific county"""
        if not county:
            return {}
            
        county_reports = Report.objects.filter(county=county)
        
        return {
            'county_info': {
                'name': county.name,
                'total_reports': county_reports.count(),
                'resolved_reports': county_reports.filter(status='resolved').count(),
                'resolution_rate': self._get_county_resolution_rate(county),
            },
            'department_breakdown': self._get_county_department_breakdown(county),
            'timeline_analytics': self._get_county_timeline_analytics(county),
        }

    def _get_county_resolution_rate(self, county):
        """Get county resolution rate"""
        county_reports = Report.objects.filter(county=county)
        resolved = county_reports.filter(status='resolved').count()
        total = county_reports.count()
        return round((resolved / total * 100), 2) if total > 0 else 0

    def _get_county_department_breakdown(self, county):
        """Get county department breakdown"""
        departments = CountyDepartment.objects.filter(county=county).annotate(
            report_count=Count('reports'),
            resolved_count=Count('reports', filter=Q(reports__status='resolved'))
        ).values('department__name', 'report_count', 'resolved_count')
        return list(departments)

    def _get_county_timeline_analytics(self, county):
        """Get county timeline analytics"""
        # Last 7 days report counts
        today = timezone.now().date()
        daily_counts = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = Report.objects.filter(county=county, created_at__date=date).count()
            daily_counts.append({'date': date.isoformat(), 'count': count})
        
        return {'daily_reports': daily_counts[::-1]}  # Reverse to show oldest first

    def _get_county_ranking(self, county):
        """Get county ranking based on performance"""
        return 5  # Placeholder

    def _get_county_response_efficiency(self, county):
        """Calculate county response efficiency"""
        return 85.2  # Placeholder

    def _get_county_satisfaction_score(self, county):
        """Get county citizen satisfaction score"""
        return 4.3  # Placeholder

    def _get_county_department_coordination(self, county):
        """Get county department coordination metrics"""
        return {
            'departments_with_reports': CountyDepartment.objects.filter(county=county, reports__isnull=False).distinct().count(),
            'avg_department_response_time': 24.5,  # Placeholder
            'interdepartmental_collaboration': 12,  # Placeholder
        }

    def _calculate_personal_engagement_score(self, user):
        """Calculate personal engagement score"""
        reports_count = user.reports.count()
        comments_count = user.comments.count()
        likes_count = user.liked_reports.count()
        
        return (reports_count * 3) + (comments_count * 2) + (likes_count * 1)

    def _calculate_personal_success_rate(self, user):
        """Calculate personal report success rate"""
        user_reports = user.reports
        resolved = user_reports.filter(status='resolved').count()
        total = user_reports.count()
        
        return round((resolved / total * 100), 2) if total > 0 else 0

    def _get_county_top_departments(self, county):
        """Get top departments for a county"""
        departments = CountyDepartment.objects.filter(county=county).annotate(
            report_count=Count('reports')
        ).order_by('-report_count')[:5].values('department__name', 'report_count')
        
        return list(departments)

    def _calculate_community_contribution(self, user):
        """Calculate community contribution score"""
        return 75  # Placeholder

    def _calculate_influence_rating(self, user):
        """Calculate user influence rating"""
        return 4.2  # Placeholder

    def _get_response_rate_to_user_reports(self, user):
        """Get response rate to user's reports"""
        user_reports = user.reports
        responded_reports = user_reports.filter(response_date__isnull=False).count()
        total_reports = user_reports.count()
        
        return round((responded_reports / total_reports * 100), 2) if total_reports > 0 else 0

# Keep your existing classes below
class RecentActivityAPI(APIView):
    """Get recent system activity for dashboard"""
    permission_classes = [IsAuthenticatedAndHasRole]

    def get(self, request):
        try:
            user = request.user
            limit = int(request.GET.get('limit', 10))

            activities = []

            # Recent reports (role-based)
            if user.is_superadmin or user.is_admin:
                recent_reports = Report.objects.select_related('reporter', 'county')[:limit]
            elif user.is_county_official and user.county:
                recent_reports = Report.objects.filter(county=user.county).select_related('reporter', 'county')[:limit]
            else:
                recent_reports = Report.objects.filter(reporter=user).select_related('reporter', 'county')[:limit]

            for report in recent_reports:
                activities.append({
                    'type': 'report_submitted',
                    'id': report.id,
                    'user': {
                        'name': report.reporter.get_full_name(),
                        'role': report.reporter.role
                    },
                    'target': {
                        'id': report.id,
                        'title': report.title,
                        'type': 'report'
                    },
                    'timestamp': report.created_at.isoformat(),
                    'metadata': {
                        'county': report.county.name,
                        'status': report.status
                    }
                })

            # Sort by timestamp and limit
            activities.sort(key=lambda x: x['timestamp'], reverse=True)
            activities = activities[:limit]

            return Response(activities, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Recent activity error: {str(e)}")
            return Response(
                {"error": "Failed to fetch recent activity"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Role-specific dashboard endpoints
class CitizenDashboardAPI(APIView):
    permission_classes = [IsAuthenticatedAndHasRole]

    def get(self, request):
        if not request.user.is_citizen:
            return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        # Return citizen-specific stats
        stats = ProfessionalDashboardStatsAPI()._get_citizen_stats(request.user)
        return Response(stats)

class OfficialDashboardAPI(APIView):
    permission_classes = [IsAuthenticatedAndHasRole]

    def get(self, request):
        if not request.user.is_county_official:
            return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        # Return official-specific stats
        stats = ProfessionalDashboardStatsAPI()._get_official_stats(request.user)
        return Response(stats)

class AdminDashboardAPI(APIView):
    permission_classes = [IsAuthenticatedAndHasRole]

    def get(self, request):
        if not (request.user.is_admin or request.user.is_superadmin):
            return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        # Return admin-specific stats
        stats = ProfessionalDashboardStatsAPI()._get_admin_stats()
        return Response(stats)