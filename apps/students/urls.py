from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path("", views.portal_home, name="portal_home"),
    path("results/", views.learning_results, name="learning_results"),
    path("results/<int:pk>/", views.learning_result_detail, name="learning_result_detail"),
    path(
        "results/<int:enrollment_id>/sessions/<int:session_id>/",
        views.learning_session_detail,
        name="learning_session_detail",
    ),
    path("products/my/", views.student_products_my, name="student_products_my"),
    path("products/", views.student_products_list, name="student_products_list"),
    path("products/<int:pk>/", views.student_product_detail, name="student_product_detail"),
    path("products/<int:pk>/public/", views.student_product_detail_public, name="student_product_detail_public"),
    path("course/<int:class_id>/", views.portal_course_detail, name="portal_course_detail"),
    path(
        "course/<int:class_id>/products-panel/",
        views.portal_course_products_panel,
        name="course_products_panel",
    ),
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
