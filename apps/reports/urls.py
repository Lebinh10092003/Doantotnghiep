from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.enrollment_summary, name="enrollment_summary"),
]
