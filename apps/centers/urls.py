from django.urls import path
from . import views

app_name = "centers"
urlpatterns = [
    path('',views.centers_manage,name="centers_manage"),
    path('add/', views.center_create_view, name="center_add"),
    path('delete/', views.center_delete_view, name="center_delete"),
    path('edit/<int:center_id>/', views.center_edit_view, name="center_edit"),
    path('<int:center_id>/detail/', views.center_detail_view, name="center_detail"),

    # URLs for Rooms
    path('rooms/', views.rooms_manage, name="rooms_manage"),
    path('rooms/add/', views.room_create_view, name="room_add"),
    path('rooms/edit/<int:room_id>/', views.room_edit_view, name="room_edit"),
    path('rooms/delete/', views.room_delete_view, name="room_delete"),
]
