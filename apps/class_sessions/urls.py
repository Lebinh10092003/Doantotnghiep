from django.urls import path
from . import views

app_name = "class_sessions"

urlpatterns = [
    path("manage/", views.manage_class_sessions, name="manage_class_sessions"),
    path("add/", views.session_create_view, name="session_add"),
    path("<int:pk>/edit/", views.session_edit_view, name="session_edit"),
    path("<int:pk>/detail/", views.session_detail_view, name="session_detail"),
    path("<int:pk>/delete/", views.session_delete_view, name="session_delete"),
]