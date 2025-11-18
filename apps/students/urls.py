from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    # Student portal
    path("", views.portal_home, name="portal_home"),
    path("course/<int:class_id>/", views.portal_course_detail, name="portal_course_detail"),
]