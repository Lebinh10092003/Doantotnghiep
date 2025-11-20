from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path("", views.portal_home, name="portal_home"),
    path("products/", views.student_products_list, name="student_products_list"),
    path("products/<int:pk>/", views.student_product_detail, name="student_product_detail"),
    path("course/<int:class_id>/", views.portal_course_detail, name="portal_course_detail"),
    path(
        "exercises/submissions/<int:pk>/edit/",
        views.submission_update,
        name="submission_update",
    ),
    path(
        "exercises/<int:exercise_id>/submissions/new/",
        views.submission_create,
        name="submission_create",
    ),
    path(
        "sessions/<int:session_id>/products/new/",
        views.product_create,
        name="product_create",
    ),
    path(
        "products/<int:pk>/edit/",
        views.product_update,
        name="product_update",
    ),
    path(
        "products/<int:pk>/delete/",
        views.product_delete,
        name="product_delete",
    ),
]
