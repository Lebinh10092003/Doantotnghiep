from django.urls import path

from . import views

app_name = "enrollments"

urlpatterns = [
    path("", views.enrollment_list, name="list"),
    path("new/", views.enrollment_create, name="create"),
    path("<int:pk>/edit/", views.enrollment_update, name="update"),
    path("<int:pk>/cancel/", views.enrollment_cancel, name="cancel"),
    path("calculate-end-date/", views.enrollment_calculate_end_date, name="calculate_end_date"),
]
