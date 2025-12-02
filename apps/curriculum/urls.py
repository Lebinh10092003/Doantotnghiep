from django.urls import path
from . import views

app_name = "curriculum"

urlpatterns = [
    # Môn học
    path("subjects/", views.subjects_manage, name="subjects_manage"),
    path("subjects/add/", views.subject_create_view, name="subject_add"),
    path("subjects/<int:subject_id>/edit/", views.subject_edit_view, name="subject_edit"),
    path("subjects/<int:subject_id>/detail/", views.subject_detail_view, name="subject_detail"),
    path("subjects/<int:subject_id>/delete/", views.subject_delete_single_view, name="subject_delete_single"),
    path("subjects/delete/", views.subject_delete_view, name="subject_delete"),
    # Học phần
    path("modules/", views.modules_manage, name="modules_manage"),
    path("modules/add/", views.module_create_view, name="module_add"),
    path("modules/<int:module_id>/edit/", views.module_edit_view, name="module_edit"),
    path("modules/<int:module_id>/detail/", views.module_detail_view, name="module_detail"),
    path("modules/delete/", views.module_delete_view, name="module_delete"),
    # Bài học
    path("lessons/", views.lessons_manage, name="lessons_manage"),
    path("lessons/add/", views.lesson_create_view, name="lesson_add"),
    path("lessons/<int:lesson_id>/edit/", views.lesson_edit_view, name="lesson_edit"),
    path("lessons/<int:lesson_id>/detail/", views.lesson_detail_view, name="lesson_detail"),
    path("lessons/<int:lesson_id>/delete/", views.lesson_delete_single_view, name="lesson_delete_single"),
    path("lessons/delete/", views.lesson_delete_view, name="lesson_delete"),
    path("lessons/<int:lesson_id>/content/", views.lesson_content_edit_view, name="lesson_content_edit"),
    path("lessons/<int:lesson_id>/lecture/delete/", views.lecture_delete_view, name="lecture_delete"),
    path("lessons/<int:lesson_id>/exercise/delete/", views.exercise_delete_view, name="exercise_delete"),

    # Nhập/Xuất chương trình
    path("curriculum/export/", views.export_curriculum_view, name="curriculum_export"),
    path("curriculum/import/", views.import_curriculum_view, name="curriculum_import"),
    path("curriculum/import/template/", views.import_curriculum_template_view, name="curriculum_import_template"),
]
