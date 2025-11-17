from django.urls import path
from . import views

app_name = "assessments"

urlpatterns = [
    path('update/<int:session_id>/<int:student_id>/', views.update_assessment, name='update_assessment'),
]