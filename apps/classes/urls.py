from django.urls import path
from . import views

app_name = "classes"

urlpatterns = [
    path("manage/", views.manage_classes, name="manage_classes"),
    path("add/", views.class_create_view, name="class_add"),
    path("<int:pk>/edit/", views.class_edit_view, name="class_edit"),
    path("<int:pk>/detail/", views.class_detail_view, name="class_detail"),
    path("<int:pk>/delete/", views.class_delete_view, name="class_delete"),
    path("<int:pk>/generate-sessions/", views.generate_sessions_view, name="generate_sessions"),
]