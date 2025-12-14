import json
import os
from datetime import date
from io import BytesIO
from urllib.parse import urlparse

import pandas as pd
import requests
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.base import ContentFile
from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from .models import Subject, Module, Lesson, Lecture, Exercise
from apps.students.models import StudentExerciseSubmission
from apps.class_sessions.models import ClassSession
from .forms import SubjectForm, ModuleForm, LessonForm, LectureForm, ExerciseForm, ImportCurriculumForm
from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request
from apps.filters.models import SavedFilter
from apps.filters.utils import build_filter_badges, determine_active_filter_name
from .filters import SubjectFilter, ModuleFilter, LessonFilter

# Danh sách môn học
@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def subjects_manage(request):
    subject_filter = SubjectFilter(request.GET, queryset=Subject.objects.all())
    qs = subject_filter.qs.order_by("code")

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    saved_filters = SavedFilter.objects.filter(model_name="Subject").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    active_filter_name = determine_active_filter_name(request, saved_filters)
    active_filter_badges = build_filter_badges(subject_filter)

    query_params = request.GET.copy()
    query_params._mutable = True
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "filter": subject_filter,
        "model_name": "Subject",
        "current_query_params": query_params.urlencode(),
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
    }

    if is_htmx_request(request):
        return render(request, "_subjects_filterable_content.html", context)

    return render(request, "manage_subjects.html", context)

# Tạo môn học
@login_required
@permission_required("curriculum.add_subject", raise_exception=True)
def subject_create_view(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-subjects-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã tạo Môn học '{subject.name}'"}
            })
            return resp
        response = render(request, "_subject_form.html", {"form": form, "is_create": True}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể tạo Môn học",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    form = SubjectForm()
    return render(request, "_subject_form.html", {"form": form, "is_create": True})

# Chỉnh sửa môn học
@login_required
@permission_required("curriculum.change_subject", raise_exception=True)
def subject_edit_view(request, subject_id: int):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == "POST":
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            subject = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-subjects-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã cập nhật Môn học '{subject.name}'"}
            })
            return resp
        response = render(request, "_subject_form.html", {"form": form, "subject": subject}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật Môn học",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    form = SubjectForm(instance=subject)
    return render(request, "_subject_form.html", {"form": form, "subject": subject})

# Chi tiết môn học
@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def subject_detail_view(request, subject_id: int):
    subject = get_object_or_404(Subject.objects.prefetch_related('modules'), id=subject_id)
    context = {"subject": subject}
    return render(request, "_subject_detail.html", context)

# Xóa môn học
@login_required
@permission_required("curriculum.delete_subject", raise_exception=True)
def subject_delete_view(request):
    ids = request.POST.getlist("subject_ids[]") or request.POST.getlist("subject_ids")
    ids = list(set(ids))
    alert = {}
    if not ids:
        alert = {"icon": "info", "title": "Chưa chọn môn học nào."}
    else:
        try:
            ids_int = [int(i) for i in ids]
            qs = Subject.objects.filter(id__in=ids_int)
            count = qs.count()
            names = list(qs.values_list("name", flat=True))
            qs.delete()
            if count == 1:
                alert = {"icon": "success", "title": f"Đã xóa Môn học '{names[0]}'"}
            else:
                alert = {"icon": "success", "title": f"Đã xóa {count} Môn học"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

    resp = HttpResponse(status=200)
    resp["HX-Trigger"] = json.dumps({
        "reload-subjects-table": True, "closeSubjectModal": True, "show-sweet-alert": alert
    })
    return resp

# Xóa môn học đơn lẻ
@login_required
@permission_required("curriculum.delete_subject", raise_exception=True)
def subject_delete_single_view(request, subject_id: int):
    subject = get_object_or_404(Subject, id=subject_id)
    alert = {}
    if request.method == "POST":
        try:
            subject_name = subject.name
            subject.delete()
            alert = {"icon": "success", "title": f"Đã xóa Môn học '{subject_name}'"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({"reload-subjects-table": True, "show-sweet-alert": alert})
        return resp
    return HttpResponse(status=405) # Phương thức không được phép


# Quản lý học phần
@login_required
@permission_required("curriculum.view_module", raise_exception=True)
def modules_manage(request):
    module_filter = ModuleFilter(request.GET, queryset=Module.objects.select_related("subject"))
    qs = module_filter.qs.order_by("subject__name", "order")

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    saved_filters = SavedFilter.objects.filter(model_name="Module").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    active_filter_name = determine_active_filter_name(request, saved_filters)
    active_filter_badges = build_filter_badges(module_filter)

    query_params = request.GET.copy()
    query_params._mutable = True
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "filter": module_filter,
        "model_name": "Module",
        "current_query_params": query_params.urlencode(),
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
    }

    if is_htmx_request(request):
        return render(request, "_modules_filterable_content.html", context)

    return render(request, "manage_modules.html", context)

# Tạo học phần cho môn học 
@login_required
@permission_required("curriculum.add_module", raise_exception=True)
def module_create_view(request):
    if request.method == "POST":
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-modules-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã tạo Học phần '{module.title}'"}
            })
            return resp
        response = render(request, "_module_form.html", {"form": form, "is_create": True}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể tạo Học phần",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    initial = {}
    if request.GET.get("subject"):
        try:
            initial["subject"] = int(request.GET.get("subject"))
        except (TypeError, ValueError):
            pass
    form = ModuleForm(initial=initial)
    return render(request, "_module_form.html", {"form": form, "is_create": True})

# Chỉnh sửa học phần 
@login_required
@permission_required("curriculum.change_module", raise_exception=True)
def module_edit_view(request, module_id: int):
    module = get_object_or_404(Module, id=module_id)
    if request.method == "POST":
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            module = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-modules-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã cập nhật Học phần '{module.title}'"}
            })
            return resp
        response = render(request, "_module_form.html", {"form": form, "module": module}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật Học phần",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    form = ModuleForm(instance=module)
    return render(request, "_module_form.html", {"form": form, "module": module})

# Chi tiết học phần
@login_required
@permission_required("curriculum.view_module", raise_exception=True)
def module_detail_view(request, module_id: int):
    module = get_object_or_404(Module.objects.select_related('subject').prefetch_related('lessons'), id=module_id)
    context = {"module": module}
    return render(request, "_module_detail.html", context)

# Xóa học phần
@login_required
@permission_required("curriculum.delete_module", raise_exception=True)
def module_delete_view(request):
    ids = request.POST.getlist("module_ids[]") or request.POST.getlist("module_ids")
    ids = list(set(ids))
    alert = {}
    if not ids:
        alert = {"icon": "info", "title": "Chưa chọn học phần nào."}
    else:
        try:
            ids_int = [int(i) for i in ids]
            qs = Module.objects.filter(id__in=ids_int)
            count = qs.count()
            names = list(qs.values_list("title", flat=True))
            qs.delete()
            if count == 1:
                alert = {"icon": "success", "title": f"Đã xóa Học phần '{names[0]}'"}
            else:
                alert = {"icon": "success", "title": f"Đã xóa {count} Học phần"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

    resp = HttpResponse(status=200)
    resp["HX-Trigger"] = json.dumps({
        "reload-modules-table": True, "closeSubjectModal": True, "show-sweet-alert": alert
    })
    return resp


# Quản lý bài học
@login_required
@permission_required("curriculum.view_lesson", raise_exception=True)
def lessons_manage(request):
    lesson_filter = LessonFilter(
        request.GET,
        queryset=Lesson.objects.select_related("module", "module__subject", "lecture", "exercise"),
    )
    qs = lesson_filter.qs.order_by("module__subject__name", "module__title", "order")

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    saved_filters = SavedFilter.objects.filter(model_name="Lesson").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    active_filter_name = determine_active_filter_name(request, saved_filters)
    active_filter_badges = build_filter_badges(lesson_filter)

    query_params = request.GET.copy()
    query_params._mutable = True
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "filter": lesson_filter,
        "model_name": "Lesson",
        "current_query_params": query_params.urlencode(),
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
    }

    if is_htmx_request(request):
        return render(request, "_lessons_filterable_content.html", context)

    return render(request, "manage_lessons.html", context)

# Tạo bài học
@login_required
@permission_required("curriculum.add_lesson", raise_exception=True)
def lesson_create_view(request):
    if request.method == "POST":
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-lessons-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã tạo Bài học '{lesson.title}'"}
            })
            return resp
        response = render(request, "_lesson_form.html", {"form": form, "is_create": True}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể tạo Bài học",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    initial = {}
    if request.GET.get("module"):
        try:
            initial["module"] = int(request.GET.get("module"))
        except (TypeError, ValueError):
            pass
    form = LessonForm(initial=initial)
    return render(request, "_lesson_form.html", {"form": form, "is_create": True})

# Chỉnh sửa bài học
@login_required
@permission_required("curriculum.change_lesson", raise_exception=True)
def lesson_edit_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    if request.method == "POST":
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            lesson = form.save()
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-lessons-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã cập nhật Bài học '{lesson.title}'"}
            })
            return resp
        response = render(request, "_lesson_form.html", {"form": form, "lesson": lesson}, status=422)
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật Bài học",
                    "text": form_errors_as_text(form),
                }
            })
        return response

    form = LessonForm(instance=lesson)
    return render(request, "_lesson_form.html", {"form": form, "lesson": lesson})

# Chi tiết bài học
@login_required
@permission_required("curriculum.view_lesson", raise_exception=True)
def lesson_detail_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson.objects.select_related('module', 'module__subject', 'lecture', 'exercise'), id=lesson_id)
    exercise = None
    try:
        exercise = lesson.exercise
    except Lesson.exercise.RelatedObjectDoesNotExist:  # Quan hệ một-một có thể chưa tồn tại
        exercise = None

    exercise_submissions = []
    if exercise and request.user.is_authenticated:
        exercise_submissions = (
            StudentExerciseSubmission.objects.filter(
                student=request.user, exercise=exercise
            )
            .select_related("session")
            .order_by("-created_at")
        )
    class_session = None
    class_id = request.GET.get("class_id")
    if class_id:
        try:
            class_id_int = int(class_id)
        except (TypeError, ValueError):
            class_id_int = None
        if class_id_int:
            session_qs = (
                ClassSession.objects.filter(klass_id=class_id_int, lesson=lesson)
                .select_related("klass", "klass__main_teacher", "teacher_override")
                .order_by("date", "start_time", "pk")
            )
            if session_qs.exists():
                dated_sessions = session_qs.exclude(date__isnull=True)
                class_session = (
                    dated_sessions.filter(date__gte=date.today()).first()
                    or dated_sessions.order_by("-date", "-start_time", "-pk").first()
                    or session_qs.first()
                )

    context = {
        "lesson": lesson,
        "exercise_submissions": exercise_submissions,
        "class_id": class_id,
        "class_session": class_session,
    }
    # Phục vụ template phù hợp với ngữ cảnh lời gọi
    as_param = request.GET.get("as")
    if is_htmx_request(request):
        if as_param == "inline":
            return render(request, "lesson_detail.html", context)
        else:
            # Mặc định cho lời gọi HTMX mong chờ đánh dấu modal
            return render(request, "_lesson_detail.html", context)
    # Không phải HTMX: render biến thể toàn trang
    return render(request, "lesson_detail.html", context)

# Xóa bài học
@login_required
@permission_required("curriculum.delete_lesson", raise_exception=True)
def lesson_delete_view(request):
    ids = request.POST.getlist("lesson_ids[]") or request.POST.getlist("lesson_ids")
    ids = list(set(ids))
    alert = {}
    if not ids:
        alert = {"icon": "info", "title": "Chưa chọn bài học nào."}
    else:
        try:
            ids_int = [int(i) for i in ids]
            qs = Lesson.objects.filter(id__in=ids_int)
            count = qs.count()
            names = list(qs.values_list("title", flat=True))
            qs.delete()
            if count == 1:
                alert = {"icon": "success", "title": f"Đã xóa Bài học '{names[0]}'"}
            else:
                alert = {"icon": "success", "title": f"Đã xóa {count} Bài học"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

    resp = HttpResponse(status=200)
    resp["HX-Trigger"] = json.dumps({
        "reload-lessons-table": True, "closeSubjectModal": True, "show-sweet-alert": alert
    })
    return resp

# Xóa bài học đơn lẻ
@login_required
@permission_required("curriculum.delete_lesson", raise_exception=True)
def lesson_delete_single_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    alert = {}
    if request.method == "POST":
        try:
            lesson_title = lesson.title
            lesson.delete()
            alert = {"icon": "success", "title": f"Đã xóa Bài học '{lesson_title}'"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({"reload-lessons-table": True, "show-sweet-alert": alert})
        return resp
    return HttpResponse(status=405) # Phương thức không được phép

# Quản lý nội dung bài học (Bài giảng và Bài tập)
@login_required
@permission_required("curriculum.change_lesson", raise_exception=True) # Dùng quyền change_lesson
def lesson_content_edit_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    lecture = getattr(lesson, "lecture", None)
    exercise = getattr(lesson, "exercise", None)

    if request.method == "POST":
        # 'form_type' là input ẩn trong template để xác định form nào gửi lên
        form_type = request.POST.get("form_type")

        lecture_form = LectureForm(request.POST, request.FILES, instance=lecture, prefix="lecture")
        exercise_form = ExerciseForm(request.POST, request.FILES, instance=exercise, prefix="exercise")

        forms_are_valid = False
        if form_type == "lecture" and lecture_form.is_valid():
            lecture_instance = lecture_form.save(commit=False)
            lecture_instance.lesson = lesson
            lecture_instance.save()
            forms_are_valid = True
        elif form_type == "exercise" and exercise_form.is_valid():
            exercise_instance = exercise_form.save(commit=False)
            exercise_instance.lesson = lesson
            exercise_instance.save()
            forms_are_valid = True

        if forms_are_valid:
            resp = HttpResponse(status=200)
            resp["HX-Trigger"] = json.dumps({
                "reload-lessons-table": True,
                "closeSubjectModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã cập nhật nội dung cho '{lesson.title}'"}
            })
            return resp

    # Dùng cho GET hoặc POST không hợp lệ
    lecture_form = LectureForm(instance=lecture, prefix="lecture")
    exercise_form = ExerciseForm(instance=exercise, prefix="exercise", initial={'lesson': lesson})
    # Ẩn trường lesson vì đã xác định sẵn
    exercise_form.fields['lesson'].widget = forms.HiddenInput()

    context = {
        "lesson": lesson,
        "lecture_form": lecture_form,
        "exercise_form": exercise_form,
    }
    return render(request, "_lesson_content_form.html", context, status=422 if request.method == "POST" else 200)

# Xóa bài giảng
@login_required
@permission_required("curriculum.delete_lecture", raise_exception=True)
def lecture_delete_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    alert = {}
    if request.method == "POST":
        try:
            if hasattr(lesson, "lecture") and lesson.lecture:
                lesson.lecture.delete()
            alert = {"icon": "success", "title": f"Đã xóa Bài giảng của '{lesson.title}'"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}
        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-lessons-table": True,
            "show-sweet-alert": alert,
        })
        return resp
    return HttpResponse(status=405)

# Xóa bài tập
@login_required
@permission_required("curriculum.delete_exercise", raise_exception=True)
def exercise_delete_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    alert = {}
    if request.method == "POST":
        try:
            if hasattr(lesson, "exercise") and lesson.exercise:
                lesson.exercise.delete()
            alert = {"icon": "success", "title": f"Đã xóa Bài tập của '{lesson.title}'"}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}
        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-lessons-table": True,
            "show-sweet-alert": alert,
        })
        return resp
    return HttpResponse(status=405)


# Xuất curriculum ra file Excel
@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def export_curriculum_view(request):
    # Dựng DataFrame cho từng thực thể
    subjects_qs = Subject.objects.all().order_by("code")
    modules_qs = Module.objects.select_related("subject").all().order_by("subject__code", "order")
    lessons_qs = Lesson.objects.select_related("module", "module__subject").all().order_by("module__subject__code", "module__order", "order")
    lectures_qs = Lecture.objects.select_related("lesson", "lesson__module", "lesson__module__subject").all().order_by("lesson__module__subject__code", "lesson__module__order", "lesson__order")
    exercises_qs = Exercise.objects.select_related("lesson", "lesson__module", "lesson__module__subject").all().order_by("lesson__module__subject__code", "lesson__module__order", "lesson__order")

    subjects_df = pd.DataFrame([
        {
            "code": s.code,
            "name": s.name,
            "description": s.description or "",
            "avatar_url": s.avatar_url or "",
        }
        for s in subjects_qs
    ])

    modules_df = pd.DataFrame([
        {
            "subject_code": m.subject.code,
            "order": m.order,
            "title": m.title,
            "description": m.description or "",
            "image_url": m.image_url or "",
        }
        for m in modules_qs
    ])

    lessons_df = pd.DataFrame([
        {
            "subject_code": l.module.subject.code,
            "module_order": l.module.order,
            "order": l.order,
            "title": l.title,
            "objectives": l.objectives or "",
        }
        for l in lessons_qs
    ])

    lectures_df = pd.DataFrame([
        {
            "subject_code": lec.lesson.module.subject.code,
            "module_order": lec.lesson.module.order,
            "lesson_order": lec.lesson.order,
            "content": lec.content or "",
            "video_url": lec.video_url or "",
            # File được xuất theo đường dẫn lưu trữ để tham chiếu
            "file": lec.file.name if lec.file else "",
            "file_url": request.build_absolute_uri(lec.file.url) if lec.file else "",
        }
        for lec in lectures_qs
    ])

    exercises_df = pd.DataFrame([
        {
            "subject_code": ex.lesson.module.subject.code,
            "module_order": ex.lesson.module.order,
            "lesson_order": ex.lesson.order,
            "description": ex.description or "",
            "difficulty": ex.difficulty,
            "file": (ex.file.name if getattr(ex, "file", None) else ""),
            "file_url": request.build_absolute_uri(ex.file.url) if ex.file else (ex.link_url or ""),
        }
        for ex in exercises_qs
    ])

    # Ghi ra file Excel nhiều sheet
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Đảm bảo mỗi DataFrame có header kể cả khi trống
        (subjects_df if not subjects_df.empty else pd.DataFrame(columns=["code", "name", "description", "avatar_url"])) \
            .to_excel(writer, sheet_name="Subjects", index=False)
        (modules_df if not modules_df.empty else pd.DataFrame(columns=["subject_code", "order", "title", "description", "image_url"])) \
            .to_excel(writer, sheet_name="Modules", index=False)
        (lessons_df if not lessons_df.empty else pd.DataFrame(columns=["subject_code", "module_order", "order", "title", "objectives"])) \
            .to_excel(writer, sheet_name="Lessons", index=False)
        (lectures_df if not lectures_df.empty else pd.DataFrame(columns=["subject_code", "module_order", "lesson_order", "content", "video_url", "file", "file_url"])) \
            .to_excel(writer, sheet_name="Lectures", index=False)
        (exercises_df if not exercises_df.empty else pd.DataFrame(columns=["subject_code", "module_order", "lesson_order", "description", "difficulty", "file", "file_url"])) \
            .to_excel(writer, sheet_name="Exercises", index=False)

    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="curriculum.xlsx"'
    return response

# Nhập curriculum từ file Excel
@login_required
@permission_required("curriculum.add_subject", raise_exception=True)
def import_curriculum_view(request):
    if request.method == "POST":
        form = ImportCurriculumForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "_import_curriculum_form.html", {"form": form, "errors": ["Dữ liệu không hợp lệ."]}, status=422)

        upload = request.FILES.get("file")
        if not upload or not upload.name.lower().endswith(".xlsx"):
            form = ImportCurriculumForm()
            return render(
                request,
                "_import_curriculum_form.html",
                {"form": form, "errors": ["Vui lòng chọn file Excel (.xlsx). CSV không được hỗ trợ cho import đa sheet."]},
                status=422,
            )

        # Đọc toàn bộ sheet
        try:
            # Reset con trỏ phòng trường hợp đọc lại
            upload.seek(0)
            sheets = pd.read_excel(upload, sheet_name=None)
        except Exception as e:
            form = ImportCurriculumForm()
            return render(request, "_import_curriculum_form.html", {"form": form, "errors": [f"Không thể đọc file: {str(e)}"]}, status=422)

        errors = []

        def _download_file_to_content(url: str, prefix: str) -> tuple[str, ContentFile] | None:
            try:
                r = requests.get(url, timeout=10, stream=True)
                r.raise_for_status()
                # Thử suy ra tên file từ URL
                parsed = urlparse(url)
                base = os.path.basename(parsed.path) or prefix
                name, ext = os.path.splitext(base)
                if not ext:
                    # Đoán phần mở rộng theo content-type
                    ct = r.headers.get('Content-Type', '').lower()
                    if 'pdf' in ct:
                        ext = '.pdf'
                    elif 'ms-powerpoint' in ct or 'presentation' in ct or 'ppt' in ct:
                        ext = '.pptx'
                    elif 'msword' in ct or 'word' in ct or 'doc' in ct:
                        ext = '.docx'
                    elif 'zip' in ct:
                        ext = '.zip'
                    else:
                        ext = ''
                safe = slugify(name) or prefix
                filename = f"{safe}{ext}"
                content = ContentFile(r.content)
                return filename, content
            except Exception:
                return None
        savepoint = None
        try:
            with transaction.atomic():
                savepoint = transaction.savepoint()

                # 1) Môn học
                df = sheets.get("Subjects")
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        code = str(row.get("code") or "").strip()
                        name = str(row.get("name") or "").strip()
                        description = str(row.get("description") or "").strip()
                        avatar_url = str(row.get("avatar_url") or "").strip()
                        if not code:
                            errors.append(f"Subjects!Dòng {idx+2}: Thiếu 'code'.")
                            continue
                        subj, _ = Subject.objects.get_or_create(code=code, defaults={"name": name, "description": description})
                        # Cập nhật nếu bản ghi đã tồn tại
                        if (name and subj.name != name) or (description and subj.description != description) or (avatar_url and subj.avatar_url != avatar_url):
                            if name:
                                subj.name = name
                            subj.description = description
                            subj.avatar_url = avatar_url or None
                            subj.save()

                # 2) Học phần
                df = sheets.get("Modules")
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        subject_code = str(row.get("subject_code") or "").strip()
                        try:
                            order = int(row.get("order"))
                        except Exception:
                            order = None
                        title = str(row.get("title") or "").strip()
                        description = str(row.get("description") or "").strip()
                        image_url = str(row.get("image_url") or "").strip()
                        if not subject_code or order is None:
                            errors.append(f"Modules!Dòng {idx+2}: Thiếu 'subject_code' hoặc 'order'.")
                            continue
                        try:
                            subject = Subject.objects.get(code=subject_code)
                        except Subject.DoesNotExist:
                            errors.append(f"Modules!Dòng {idx+2}: Subject '{subject_code}' không tồn tại.")
                            continue
                        module, _ = Module.objects.get_or_create(subject=subject, order=order, defaults={"title": title, "description": description, "image_url": image_url})
                        if (title and module.title != title) or (description and module.description != description) or (image_url and (module.image_url or "") != image_url):
                            if title:
                                module.title = title
                            module.description = description
                            module.image_url = image_url or None
                            module.save()

                # 3) Bài học
                df = sheets.get("Lessons")
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        subject_code = str(row.get("subject_code") or "").strip()
                        try:
                            module_order = int(row.get("module_order"))
                        except Exception:
                            module_order = None
                        try:
                            order = int(row.get("order"))
                        except Exception:
                            order = None
                        title = str(row.get("title") or "").strip()
                        objectives = str(row.get("objectives") or "").strip()
                        if not subject_code or module_order is None or order is None:
                            errors.append(f"Lessons!Dòng {idx+2}: Thiếu 'subject_code', 'module_order' hoặc 'order'.")
                            continue
                        try:
                            subject = Subject.objects.get(code=subject_code)
                            module = Module.objects.get(subject=subject, order=module_order)
                        except (Subject.DoesNotExist, Module.DoesNotExist):
                            errors.append(f"Lessons!Dòng {idx+2}: Module ({subject_code}, {module_order}) không tồn tại.")
                            continue
                        lesson, _ = Lesson.objects.get_or_create(module=module, order=order, defaults={"title": title, "objectives": objectives})
                        if (title and lesson.title != title) or (objectives and lesson.objectives != objectives):
                            if title:
                                lesson.title = title
                            lesson.objectives = objectives
                            lesson.save()

                # 4) Bài giảng
                df = sheets.get("Lectures")
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        subject_code = str(row.get("subject_code") or "").strip()
                        try:
                            module_order = int(row.get("module_order"))
                            lesson_order = int(row.get("lesson_order"))
                        except Exception:
                            module_order = None
                            lesson_order = None
                        content = str(row.get("content") or "").strip()
                        video_url = str(row.get("video_url") or "").strip()
                        file_url = str(row.get("file_url") or "").strip()
                        if not subject_code or module_order is None or lesson_order is None:
                            errors.append(f"Lectures!Dòng {idx+2}: Thiếu 'subject_code', 'module_order' hoặc 'lesson_order'.")
                            continue
                        try:
                            subject = Subject.objects.get(code=subject_code)
                            module = Module.objects.get(subject=subject, order=module_order)
                            lesson = Lesson.objects.get(module=module, order=lesson_order)
                        except (Subject.DoesNotExist, Module.DoesNotExist, Lesson.DoesNotExist):
                            errors.append(f"Lectures!Dòng {idx+2}: Lesson ({subject_code}, {module_order}, {lesson_order}) không tồn tại.")
                            continue
                        lecture, _ = Lecture.objects.get_or_create(lesson=lesson)
                        if content:
                            lecture.content = content
                        # Thử tải file nếu có file_url
                        if file_url:
                            dl = _download_file_to_content(file_url, prefix=f"lecture-{lesson.id}")
                            if dl:
                                fname, cfile = dl
                                try:
                                    lecture.file.save(fname, cfile, save=False)
                                except Exception:
                                    # Rớt về lưu lại URL nếu lỗi
                                    if not video_url:
                                        video_url = file_url
                            else:
                                # Lưu URL để hiển thị dự phòng
                                if not video_url:
                                    video_url = file_url
                        lecture.video_url = video_url
                        lecture.save()

                # 5) Bài tập
                df = sheets.get("Exercises")
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        subject_code = str(row.get("subject_code") or "").strip()
                        try:
                            module_order = int(row.get("module_order"))
                            lesson_order = int(row.get("lesson_order"))
                        except Exception:
                            module_order = None
                            lesson_order = None
                        description = str(row.get("description") or "").strip()
                        difficulty_raw = str(row.get("difficulty") or "").strip().lower()
                        file_url = str(row.get("file_url") or "").strip()
                        if difficulty_raw in {"dễ", "de", "de~", "easy"}:
                            difficulty = "easy"
                        elif difficulty_raw in {"trung bình", "trung binh", "medium"}:
                            difficulty = "medium"
                        elif difficulty_raw in {"khó", "kho", "hard"}:
                            difficulty = "hard"
                        elif not difficulty_raw:
                            difficulty = "medium"
                        else:
                            errors.append(f"Exercises!Dòng {idx+2}: 'difficulty' không hợp lệ: {difficulty_raw}.")
                            continue

                        if not subject_code or module_order is None or lesson_order is None:
                            errors.append(f"Exercises!Dòng {idx+2}: Thiếu 'subject_code', 'module_order' hoặc 'lesson_order'.")
                            continue
                        try:
                            subject = Subject.objects.get(code=subject_code)
                            module = Module.objects.get(subject=subject, order=module_order)
                            lesson = Lesson.objects.get(module=module, order=lesson_order)
                        except (Subject.DoesNotExist, Module.DoesNotExist, Lesson.DoesNotExist):
                            errors.append(f"Exercises!Dòng {idx+2}: Lesson ({subject_code}, {module_order}, {lesson_order}) không tồn tại.")
                            continue
                        exercise, _ = Exercise.objects.get_or_create(lesson=lesson)
                        if description:
                            exercise.description = description if pd.notna(description) else ""
                        exercise.difficulty = difficulty
                        # Thử tải file đính kèm
                        if file_url:
                            dl = _download_file_to_content(file_url, prefix=f"exercise-{lesson.id}")
                            if dl:
                                fname, cfile = dl
                                try:
                                    exercise.file.save(fname, cfile, save=False)
                                    exercise.link_url = ""
                                except Exception:
                                    exercise.link_url = file_url
                            else:
                                exercise.link_url = file_url
                        exercise.save()

                # Nếu có lỗi thì rollback
                if errors:
                    transaction.savepoint_rollback(savepoint)
                else:
                    transaction.savepoint_commit(savepoint)

        except Exception as e:
            errors.append(str(e))
            if savepoint:
                transaction.savepoint_rollback(savepoint)

        if errors:
            form = ImportCurriculumForm()
            return render(request, "_import_curriculum_form.html", {"form": form, "errors": errors}, status=422)

        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-subjects-table": True,
            "show-sweet-alert": {"icon": "success", "title": "Import Chương trình thành công!"},
            "closeSubjectModal": True,
        })
        return resp

    # Xử lý GET
    form = ImportCurriculumForm()
    return render(request, "_import_curriculum_form.html", {"form": form})

# Tải mẫu file nhập curriculum 
@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def import_curriculum_template_view(request):
    # File template chỉ gồm header trống
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(columns=["code", "name", "description", "avatar_url"]).to_excel(writer, sheet_name="Subjects", index=False)
        pd.DataFrame(columns=["subject_code", "order", "title", "description", "image_url"]).to_excel(writer, sheet_name="Modules", index=False)
        pd.DataFrame(columns=["subject_code", "module_order", "order", "title", "objectives"]).to_excel(writer, sheet_name="Lessons", index=False) 
        pd.DataFrame(columns=["subject_code", "module_order", "lesson_order", "content", "video_url", "file_url"]).to_excel(writer, sheet_name="Lectures", index=False)
        pd.DataFrame(columns=["subject_code", "module_order", "lesson_order", "description", "difficulty", "file_url"]).to_excel(writer, sheet_name="Exercises", index=False) 
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="curriculum_import_template.xlsx"'
    return response
