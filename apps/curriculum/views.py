import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django import forms

from .models import Subject, Module, Lesson, Lecture, Exercise
from .forms import SubjectForm, ModuleForm, LessonForm, LectureForm, ExerciseForm


def is_htmx_request(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )


# Subjects
@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def subjects_manage(request):
    q = request.GET.get("q", "").strip()
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    qs = Subject.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))

    paginator = Paginator(qs.order_by("code"), per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    context = {"page_obj": page_obj, "paginator": paginator, "q": q, "per_page": per_page}

    if is_htmx_request(request):
        return render(request, "_subjects_table.html", context)

    return render(request, "manage_subjects.html", context)


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
        return render(request, "_subject_form.html", {"form": form, "is_create": True}, status=422)

    form = SubjectForm()
    return render(request, "_subject_form.html", {"form": form, "is_create": True})


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
        return render(request, "_subject_form.html", {"form": form, "subject": subject}, status=422)

    form = SubjectForm(instance=subject)
    return render(request, "_subject_form.html", {"form": form, "subject": subject})


@login_required
@permission_required("curriculum.view_subject", raise_exception=True)
def subject_detail_view(request, subject_id: int):
    subject = get_object_or_404(Subject.objects.prefetch_related('modules'), id=subject_id)
    context = {"subject": subject}
    return render(request, "_subject_detail.html", context)


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
    return HttpResponse(status=405) # Method Not Allowed


# Modules
@login_required
@permission_required("curriculum.view_module", raise_exception=True)
def modules_manage(request):
    q = request.GET.get("q", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    qs = Module.objects.select_related("subject").all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(subject__name__icontains=q) | Q(subject__code__icontains=q))
    if subject_id:
        try:
            qs = qs.filter(subject_id=int(subject_id))
        except (TypeError, ValueError):
            pass

    paginator = Paginator(qs.order_by("subject__name", "order"), per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    subjects = Subject.objects.order_by("name").all()
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "per_page": per_page,
        "subjects": subjects,
        "selected_subject": subject_id,
    }

    if is_htmx_request(request):
        return render(request, "_modules_table.html", context)

    return render(request, "manage_modules.html", context)


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
        return render(request, "_module_form.html", {"form": form, "is_create": True}, status=422)

    initial = {}
    if request.GET.get("subject"):
        try:
            initial["subject"] = int(request.GET.get("subject"))
        except (TypeError, ValueError):
            pass
    form = ModuleForm(initial=initial)
    return render(request, "_module_form.html", {"form": form, "is_create": True})


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
        return render(request, "_module_form.html", {"form": form, "module": module}, status=422)

    form = ModuleForm(instance=module)
    return render(request, "_module_form.html", {"form": form, "module": module})


@login_required
@permission_required("curriculum.view_module", raise_exception=True)
def module_detail_view(request, module_id: int):
    module = get_object_or_404(Module.objects.select_related('subject').prefetch_related('lessons'), id=module_id)
    context = {"module": module}
    return render(request, "_module_detail.html", context)


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


# Lessons
@login_required
@permission_required("curriculum.view_lesson", raise_exception=True)
def lessons_manage(request):
    q = request.GET.get("q", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    module_id = request.GET.get("module", "").strip()
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    qs = Lesson.objects.select_related("module", "module__subject", "lecture", "exercise").all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(module__title__icontains=q) | Q(module__subject__name__icontains=q) | Q(module__subject__code__icontains=q))
    if subject_id:
        try:
            qs = qs.filter(module__subject_id=int(subject_id))
        except (TypeError, ValueError):
            pass
    if module_id:
        try:
            qs = qs.filter(module_id=int(module_id))
        except (TypeError, ValueError):
            pass

    paginator = Paginator(qs.order_by("module__subject__name", "module__title", "order"), per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    subjects = Subject.objects.order_by("name").all()
    modules = Module.objects.order_by("title").all()
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "per_page": per_page,
        "subjects": subjects,
        "selected_subject": subject_id,
        "modules": modules,
        "selected_module": module_id,
    }

    if is_htmx_request(request):
        return render(request, "_lessons_table.html", context)

    return render(request, "manage_lessons.html", context)


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
        return render(request, "_lesson_form.html", {"form": form, "is_create": True}, status=422)

    initial = {}
    if request.GET.get("module"):
        try:
            initial["module"] = int(request.GET.get("module"))
        except (TypeError, ValueError):
            pass
    form = LessonForm(initial=initial)
    return render(request, "_lesson_form.html", {"form": form, "is_create": True})


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
        return render(request, "_lesson_form.html", {"form": form, "lesson": lesson}, status=422)

    form = LessonForm(instance=lesson)
    return render(request, "_lesson_form.html", {"form": form, "lesson": lesson})


@login_required
@permission_required("curriculum.view_lesson", raise_exception=True)
def lesson_detail_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson.objects.select_related('module', 'module__subject', 'lecture', 'exercise'), id=lesson_id)
    context = {"lesson": lesson}
    return render(request, "_lesson_detail.html", context)


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
    return HttpResponse(status=405) # Method Not Allowed


@login_required
@permission_required("curriculum.change_lesson", raise_exception=True) # Uses change_lesson perm
def lesson_content_edit_view(request, lesson_id: int):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    lecture = getattr(lesson, "lecture", None)
    exercise = getattr(lesson, "exercise", None)

    if request.method == "POST":
        # 'form_type' is a hidden input in the template to know which form was submitted
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

    # GET request or invalid POST
    lecture_form = LectureForm(instance=lecture, prefix="lecture")
    exercise_form = ExerciseForm(instance=exercise, prefix="exercise", initial={'lesson': lesson})
    # Hide the lesson field in the form as it's already known
    exercise_form.fields['lesson'].widget = forms.HiddenInput()

    context = {
        "lesson": lesson,
        "lecture_form": lecture_form,
        "exercise_form": exercise_form,
    }
    return render(request, "_lesson_content_form.html", context, status=422 if request.method == "POST" else 200)
