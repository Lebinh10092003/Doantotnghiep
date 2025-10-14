from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.common.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("centers/", include("apps.centers.urls")),
    path("students/", include("apps.students.urls")),
    path("teachers/", include("apps.teachers.urls")),
    path("parents/", include("apps.parents.urls")),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
