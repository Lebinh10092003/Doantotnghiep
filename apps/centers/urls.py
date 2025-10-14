from django.urls import path
from . import views

app_name = "centers"
urlpatterns = [
    path('',views.centers_manage,name="centers_manage")
]
