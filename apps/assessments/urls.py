from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    path("", views.assessment_list, name="assessment_list"),
    path("students/", views.student_results, name="student_results"),
    path("reports/summary/", views.assessment_summary, name="assessment_summary"),
    path("update/<int:session_id>/<int:student_id>/", views.update_assessment, name="update_assessment"),
]