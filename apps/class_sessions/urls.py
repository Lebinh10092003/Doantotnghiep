from django.urls import path
from . import views

app_name = "class_sessions"

urlpatterns = [
    path("manage/", views.manage_class_sessions, name="manage_class_sessions"),
    # Schedules
    path("calendar/my/", views.my_schedule_view, name="my_schedule"),
    path("calendar/teaching/", views.teaching_schedule_view, name="teaching_schedule"),
    path("calendar/teaching/classes/", views.teaching_classes_view, name="teaching_classes"),
    path("add/", views.session_create_view, name="session_add"),
    path("<int:pk>/edit/", views.session_edit_view, name="session_edit"),
    path("<int:pk>/detail/", views.session_detail_view, name="session_detail"),
    path("<int:pk>/delete/", views.session_delete_view, name="session_delete"),
    path(
        "student-modal/<int:session_id>/<int:student_id>/",
        views.student_attendance_assessment_modal,
        name="student_attendance_assessment_modal",
    ),
    path(
        "update-student-status/<int:session_id>/<int:student_id>/", 
        views.update_student_session_status, 
        name="update_student_session_status"
    ),
]
