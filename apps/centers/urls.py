from django.urls import path
from . import views

app_name = "centers"
urlpatterns = [
    path('',views.centers_manage,name="centers_manage"),
    path('add/', views.center_create_view, name="center_add"),
    path('delete/', views.center_delete_view, name="center_delete"),
    path('edit/<int:center_id>/', views.center_edit_view, name="center_edit"),
]
