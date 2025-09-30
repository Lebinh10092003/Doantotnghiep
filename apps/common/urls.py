from django.urls import path
from . import views

app_name = "common"

urlpatterns = [
    path("", views.home, name="home"),
]
