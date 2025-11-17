from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    path('update/<int:session_id>/<int:student_id>/', views.update_attendance, name='update_attendance'),
]