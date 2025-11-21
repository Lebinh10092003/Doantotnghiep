from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.common.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("centers/", include("apps.centers.urls")),
    path("curriculum/", include("apps.curriculum.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("assessments/", include("apps.assessments.urls")),
    path("students/", include("apps.students.urls")),
    path("teachers/", include("apps.teachers.urls")),
    path("parents/", include("apps.parents.urls")),
    path("classes/", include("apps.classes.urls")),
    path("sessions/", include("apps.class_sessions.urls")),
    path("filters/", include("apps.filters.urls")),
    path("enrollments/", include("apps.enrollments.urls")),
    path("reports/", include("apps.reports.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
