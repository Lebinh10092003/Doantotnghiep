from django.urls import path
from . import views

app_name = "filters"

urlpatterns = [
    path("save/", views.save_filter_view, name="save_filter"),
    path("delete/<int:pk>/", views.delete_filter_view, name="delete_filter"),
]