from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.enrollment_summary, name="enrollment_summary"),
    path("students/", views.student_report, name="student_report"),
    path("students/pdf/", views.student_report_pdf, name="student_report_pdf"),
    path("students/<int:pk>/", views.student_report_detail, name="student_report_detail"),
    path(
        "students/<int:enrollment_id>/sessions/<int:session_id>/",
        views.student_session_detail,
        name="student_session_detail",
    ),
    path("revenue/", views.revenue_report, name="revenue_report"),
    path("teaching-hours/", views.teaching_hours_report, name="teaching_hours_report"),
    path("class-activity/", views.class_activity_report, name="class_activity_report"),
]
