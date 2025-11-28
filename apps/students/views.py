# apps/students/views.py
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseForbidden

from apps.classes.models import Class
from apps.class_sessions.models import ClassSession
from apps.enrollments.models import Enrollment
from apps.accounts.models import ParentStudentRelation
from .filters import StudentProductFilter
from .models import StudentProduct, StudentExerciseSubmission
from .forms import StudentProductForm, StudentExerciseSubmissionForm
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
import json
from django.http import HttpResponse
from django.urls import reverse
from apps.common.utils.http import is_htmx_request

def _week_range(center_date: date | None = None):
    """
    Trả về (start, end) là thứ 2 -> CN của tuần chứa center_date.
    """
    today = center_date or date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end

def _product_role_flags(user):
    role = (getattr(user, "role", "") or "").upper()
    in_group = user.groups.filter
    return {
        "role": role,
        "is_student": role == "STUDENT" or in_group(name__iexact="student").exists(),
        "is_parent": role == "PARENT" or in_group(name__iexact="parent").exists(),
        "is_teacher": role == "TEACHER" or in_group(name__iexact="teacher").exists(),
        "is_assistant": role == "ASSISTANT" or in_group(name__iexact="assistant").exists(),
        "can_manage_all": user.has_perm("students.view_studentproduct"),
    }

def _base_product_queryset():
    return StudentProduct.objects.select_related(
        "student",
        "session",
        "session__klass",
        "session__klass__subject",
        "session__klass__center",
    )

def _related_products_queryset(user):
    flags = _product_role_flags(user)
    qs = _base_product_queryset()
    if flags["is_student"]:
        return qs.filter(student=user)
    if flags["is_parent"]:
        child_ids = ParentStudentRelation.objects.filter(parent=user).values_list("student_id", flat=True)
        return qs.filter(student_id__in=child_ids)
    if flags["is_teacher"] or flags["is_assistant"]:
        return qs.filter(
            Q(session__klass__main_teacher=user)
            | Q(session__klass__assistants=user)
            | Q(session__teacher_override=user)
            | Q(session__assistants=user)
        )
    return qs

def _render_products_page(request, products, flags, page_title, page_description):
    order = request.GET.get("order", "desc")

    product_filter = StudentProductFilter(request.GET, queryset=products)
    products = product_filter.qs

    sort_field = "created_at" if order == "asc" else "-created_at"
    products = products.order_by(sort_field)

    active_filter_badges = []
    if product_filter.form.is_bound:
        for name, value in product_filter.form.cleaned_data.items():
            if value and name in product_filter.form.fields:
                field_label = product_filter.form.fields[name].label or name
                display_value = ""
                field = product_filter.form.fields[name]
                if hasattr(value, "name"):
                    display_value = str(value)
                elif isinstance(value, str):
                    display_value = value
                elif hasattr(value, "strftime"):
                    display_value = value.strftime("%d/%m/%Y")
                if display_value:
                    active_filter_badges.append(
                        {"label": field_label, "value": display_value, "key": name}
                    )

    try:
        per_page = int(request.GET.get("per_page", 9))
        if per_page <= 0:
            per_page = 9
    except (TypeError, ValueError):
        per_page = 9

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    from django.core.paginator import Paginator, EmptyPage

    paginator = Paginator(products, per_page)
    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(1)

    query_params_no_page = request.GET.copy()
    for key in ["page"]:
        query_params_no_page.pop(key, None)

    context = {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "is_student": flags["is_student"],
        "can_view_all": flags["can_manage_all"] and not (flags["is_student"] or flags["is_parent"] or flags["is_teacher"] or flags["is_assistant"]),
        "filter": product_filter,
        "model_name": "StudentProduct",
        "active_filter_name": None,
        "active_filter_badges": active_filter_badges,
        "current_query_params": query_params_no_page.urlencode(),
        "filter_params": {
            "order": order,
        },
        "page_title": page_title,
        "page_description": page_description,
        "list_url": request.path,
        "page_breadcrumb_url": request.path,
        "page_breadcrumb_label": page_title,
    }

    if is_htmx_request(request):
        return render(request, "_student_products_content.html", context)
    return render(request, "student_products_list.html", context)


@login_required
def portal_home(request):
    """
    Trang portal học sinh:
    - Lịch học dạng tuần + chọn ngày (calendar ngang).
    - Card các lớp đang học với giáo viên.
    """
    user = request.user

    # Ngày đang được chọn (trên thanh lịch)
    day_str = request.GET.get("day")
    if not day_str or day_str == "today":
        selected_date = date.today()
    else:
        try:
            selected_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = date.today()

    # Tính tuần chứa selected_date
    start, end = _week_range(selected_date)
    week_days = [start + timedelta(days=i) for i in range(7)]

    # Các buổi học trong tuần của học sinh
    week_sessions = (
        ClassSession.objects.filter(
            klass__enrollments__student=user,
            date__gte=start,
            date__lte=end,
        )
        .select_related("klass", "klass__subject", "klass__center")
        .order_by("date", "start_time")
    )

    # Các buổi học trong đúng ngày đang chọn
    selected_sessions = [s for s in week_sessions if s.date == selected_date]

    # Những ngày trong tuần có buổi học (dùng để hiện chấm tròn dưới ngày)
    session_dates = {s.date for s in week_sessions}

    # Lớp đang học
    enrollments = (
        Enrollment.objects.filter(student=user, active=True)
        .select_related("klass", "klass__subject", "klass__main_teacher")
        .order_by("joined_at")
    )

    class_cards = []
    for en in enrollments:
        next_session = (
            ClassSession.objects.filter(klass=en.klass, date__gte=date.today())
            .order_by("date", "start_time")
            .first()
        )
        class_cards.append(
            {
                "klass": en.klass,
                "next_session": next_session,
            }
        )

    # Ngày đại diện cho tuần trước / tuần sau (dùng cho nút <>)
    prev_week_day = selected_date - timedelta(days=7)
    next_week_day = selected_date + timedelta(days=7)

    context = {
        # Lịch
        "sessions": week_sessions,
        "start": start,
        "end": end,
        "week_days": week_days,
        "selected_date": selected_date,
        "selected_sessions": selected_sessions,
        "session_dates": session_dates,
        "prev_week_str": prev_week_day.strftime("%Y-%m-%d"),
        "next_week_str": next_week_day.strftime("%Y-%m-%d"),
        # Lớp
        "class_cards": class_cards,
    }
    return render(request, "student_home.html", context)


@login_required
def portal_course_detail(request, class_id: int):
    """
    Trang chi tiết khóa học của học sinh.
    - Thông tin lớp / môn / giáo viên.
    - Buổi học sắp tới nhất (upcoming session).
    - Nội dung bài học (lesson + lecture).
    - Bài tập của bài học.
    - Sản phẩm học sinh theo buổi / cả khóa.
    """
    user = request.user

    klass = get_object_or_404(
        Class.objects.select_related("subject", "center", "main_teacher"),
        id=class_id,
    )

    # Học sinh phải đang học lớp này
    if not Enrollment.objects.filter(student=user, klass=klass, active=True).exists():
        return render(request, "not_enrolled.html", {"klass": klass})

    # Buổi học sắp tới nhất
    upcoming: ClassSession | None = (
        ClassSession.objects.filter(klass=klass, date__gte=date.today())
        .select_related("lesson")
        .order_by("date", "start_time")
        .first()
    )

    subject = klass.subject
    modules = subject.modules.prefetch_related("lessons").all()

    # Lấy bài học, bài giảng, bài tập (nếu có)
    lesson = upcoming.lesson if (upcoming and upcoming.lesson_id) else None
    lecture = None
    exercise = None

    if lesson:
        try:
            lecture = lesson.lecture  # OneToOne, có thể chưa tồn tại
        except ObjectDoesNotExist:
            lecture = None

        try:
            exercise = lesson.exercise
        except ObjectDoesNotExist:
            exercise = None

    # Sản phẩm học sinh trong buổi sắp tới
    session_products = StudentProduct.objects.none()
    latest_product = None
    if upcoming:
        session_products = (
            StudentProduct.objects.filter(session=upcoming, student=user)
            .select_related("session", "student")
            .all()
        )
        latest_product = session_products.first()
    my_products = (
        StudentProduct.objects.filter(student=user, session__klass=klass)
        .select_related("session", "student")
        .order_by("-created_at")
    )

    exercise_submissions = StudentExerciseSubmission.objects.none()
    latest_submission = None
    if exercise:
        exercise_submissions = (
            StudentExerciseSubmission.objects.filter(student=user, exercise=exercise)
            .select_related("session")
            .order_by("-created_at")
        )
        latest_submission = exercise_submissions.first()

    context = {
        "klass": klass,
        "subject": subject,
        "modules": modules,
        "upcoming": upcoming,
        "lesson": lesson,
        "lecture": lecture,
        "exercise": exercise,
        "exercise_submissions": exercise_submissions,
        "latest_submission": latest_submission,
        "session_products": session_products,
        "latest_product": latest_product,
        "my_products": my_products,
    }
    return render(request, "course_detail.html", context)


@login_required
def product_create(request, session_id: int):
    # Danh sách buổi học của học sinh
    today = date.today()
    available_sessions = (
        ClassSession.objects.filter(
            klass__enrollments__student=request.user,
            klass__enrollments__active=True,
            date__lte=today,
        )
        .select_related("klass", "klass__subject")
        .order_by("-date", "-start_time")
    )
    session = None
    if session_id and session_id != 0:
        session = get_object_or_404(available_sessions, id=session_id)

    if not available_sessions.exists():
        return HttpResponseForbidden("Bạn chưa có buổi học nào để đăng sản phẩm.")

    if session:
        existing_product = StudentProduct.objects.filter(session=session, student=request.user).first()
        if existing_product:
            return redirect("students:product_update", pk=existing_product.pk)

    if request.method == "POST":
        form = StudentProductForm(request.POST, request.FILES)
        if form.is_valid():
            selected_session_id = request.POST.get("session_id") or (session.id if session else None)
            if not selected_session_id:
                return HttpResponseForbidden("Vui lòng chọn buổi học.")
            try:
                selected_session = available_sessions.get(id=selected_session_id)
            except ClassSession.DoesNotExist:
                return HttpResponseForbidden("Buổi học không hợp lệ.")

            product = form.save(commit=False)
            product.session = selected_session
            product.student = request.user
            product.save()

            if request.headers.get("HX-Request") == "true":
                resp = HttpResponse(status=204)
                resp["HX-Trigger"] = json.dumps({"reload-products": True, "closeProductModal": True})
                return resp
            return redirect("students:portal_course_detail", class_id=session.klass.id)
    else:
        form = StudentProductForm()

    template = "_student_product_form.html" if request.headers.get("HX-Request") == "true" else "student_product_form.html"
    return render(
        request,
        template,
        {
            "form": form,
            "session": session,
            "available_sessions": available_sessions,
            "is_create": True,
        },
    )


@login_required
def submission_create(request, exercise_id: int):
    from apps.curriculum.models import Exercise

    exercise = get_object_or_404(Exercise, id=exercise_id)
    session_id = request.GET.get("session_id")
    session = None
    if session_id:
        session = get_object_or_404(ClassSession, id=session_id)
        if not Enrollment.objects.filter(student=request.user, klass=session.klass, active=True).exists():
            return HttpResponseForbidden("Bạn không có quyền nộp bài cho lớp này.")
    return_class_id = (
        request.GET.get("class_id")
        or request.POST.get("class_id")
        or (session.klass.id if session else None)
    )

    if request.method == "POST":
        form = StudentExerciseSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.exercise = exercise
            submission.student = request.user
            submission.session = session
            submission.save()

            class_id = return_class_id
            redirect_to_course = None
            if class_id:
                redirect_to_course = request.build_absolute_uri(
                    reverse("students:portal_course_detail", kwargs={"class_id": class_id})
                )
                redirect_to_course += "#pane-exercise"

            if request.headers.get("HX-Request") == "true":
                resp = HttpResponse("")
                trigger = {
                    "show-sweet-alert": {
                        "icon": "success",
                        "title": "Đã nộp bài tập",
                        "text": f"Bản nộp của bạn đã được lưu \"{submission.title}\".",
                        "redirect": redirect_to_course
                            or request.build_absolute_uri(reverse("students:portal_home")),
                    }
                }
                resp["HX-Trigger"] = json.dumps(trigger)
                return resp

            if class_id:
                return redirect("students:portal_course_detail", class_id=class_id)
            return redirect("students:portal_home")
    else:
        form = StudentExerciseSubmissionForm()

    return render(
        request,
        "student_submission_form.html",
        {
            "form": form,
            "exercise": exercise,
            "session": session,
            "klass": session.klass if session else None,
            "is_create": True,
            "return_class_id": return_class_id,
        },
    )


@login_required
def submission_update(request, pk: int):
    submission = get_object_or_404(StudentExerciseSubmission, pk=pk)
    if submission.student_id != request.user.id:
        return HttpResponseForbidden("Bạn chỉ có thể chỉnh sửa bài tập của mình.")

    return_class_id = (
        request.GET.get("class_id")
        or request.POST.get("class_id")
        or (submission.session.klass.id if submission.session else None)
    )

    if request.method == "POST":
        form = StudentExerciseSubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            new_file = form.cleaned_data.get("file")
            old_file = submission.file
            form.save()
            if new_file and old_file and old_file.name != new_file.name:
                old_file.delete(save=False)

            class_id = return_class_id
            redirect_to_course = None
            if class_id:
                redirect_to_course = request.build_absolute_uri(
                    reverse("students:portal_course_detail", kwargs={"class_id": class_id})
                )
                redirect_to_course += "#pane-exercise"

            if request.headers.get("HX-Request") == "true":
                resp = HttpResponse("")
                trigger = {
                    "show-sweet-alert": {
                        "icon": "success",
                        "title": "Bài tập đã được cập nhật",
                        "text": f"Bản nộp \"{submission.title}\" đã cập nhật.",
                        "redirect": redirect_to_course
                            or request.build_absolute_uri(reverse("students:portal_home")),
                    }
                }
                resp["HX-Trigger"] = json.dumps(trigger)
                return resp

            if class_id:
                return redirect("students:portal_course_detail", class_id=class_id)
            return redirect("students:portal_home")
    else:
        form = StudentExerciseSubmissionForm(instance=submission)

    return render(
        request,
        "student_submission_form.html",
        {
            "form": form,
            "exercise": submission.exercise,
            "session": submission.session,
            "klass": submission.session.klass if submission.session else None,
            "is_create": False,
            "submission": submission,
            "return_class_id": return_class_id,
        },
    )


@login_required
def product_update(request, pk: int):
    product = get_object_or_404(StudentProduct, pk=pk)
    if product.student_id != request.user.id:
        return HttpResponseForbidden("Bạn chỉ có thể sửa sản phẩm của mình.")

    today = date.today()
    available_sessions = (
        ClassSession.objects.filter(
            klass__enrollments__student=request.user,
            klass__enrollments__active=True,
            date__lte=today,
        )
        .select_related("klass", "klass__subject")
        .order_by("-date", "-start_time")
    )

    if request.method == "POST":
        form = StudentProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            selected_session_id = request.POST.get("session_id") or product.session_id
            try:
                selected_session = available_sessions.get(id=selected_session_id)
            except ClassSession.DoesNotExist:
                return HttpResponseForbidden("Buổi học không hợp lệ.")
            new_file = form.cleaned_data.get("file")
            old_file = product.file
            prod = form.save(commit=False)
            prod.session = selected_session
            prod.save()
            if new_file and old_file and old_file.name != new_file.name:
                old_file.delete(save=False)

            if request.headers.get("HX-Request") == "true":
                resp = HttpResponse(status=204)
                resp["HX-Trigger"] = json.dumps({"reload-products": True, "closeProductModal": True})
                return resp

            return redirect("students:portal_course_detail", class_id=product.session.klass.id)
    else:
        form = StudentProductForm(instance=product)

    template = "_student_product_form.html" if request.headers.get("HX-Request") == "true" else "_student_product_form.html"
    return render(
        request,
        template,
        {
            "form": form,
            "session": product.session,
            "available_sessions": available_sessions,
            "is_create": False,
        },
    )


@login_required
def product_delete(request, pk: int):
    product = get_object_or_404(StudentProduct, pk=pk)
    if product.student_id != request.user.id:
        return HttpResponseForbidden("Bạn chỉ có thể xóa sản phẩm của mình.")

    class_id = product.session.klass.id
    if request.method == "POST":
        product.delete()
        # If HTMX, use HX-Trigger to show alert and redirect via custom-events
        if request.headers.get("HX-Request"):
            resp = HttpResponse("")
            trigger = {
                "show-sweet-alert": {
                    "icon": "success",
                    "title": "Đã xóa dự án",
                    "redirect": request.build_absolute_uri(
                        redirect("students:portal_course_detail", class_id=class_id).url
                    ),
                }
            }
            resp["HX-Trigger"] = json.dumps(trigger)
            return resp
        return redirect("students:portal_course_detail", class_id=class_id)

    return redirect("students:portal_course_detail", class_id=class_id)


@login_required
def student_products_list(request):
    user = request.user
    flags = _product_role_flags(user)
    if not (flags["is_student"] or flags["is_parent"] or flags["is_teacher"] or flags["is_assistant"] or flags["can_manage_all"]):
        raise PermissionDenied("Bạn không có quyền xem danh sách sản phẩm.")

    products = _related_products_queryset(user)
    if not (flags["is_student"] or flags["is_parent"] or flags["is_teacher"] or flags["is_assistant"]) and flags["can_manage_all"]:
        products = _base_product_queryset()

    return _render_products_page(
        request,
        products,
        flags,
        page_title="Sản phẩm học sinh",
        page_description="Xem tất cả sản phẩm học sinh với bộ lọc đầy đủ.",
    )


@login_required
def student_products_my(request):
    user = request.user
    flags = _product_role_flags(user)
    if not (flags["is_student"] or flags["is_parent"] or flags["is_teacher"] or flags["is_assistant"] or flags["can_manage_all"]):
        raise PermissionDenied("Bạn không có quyền xem danh sách sản phẩm.")

    products = _related_products_queryset(user)
    if not (flags["is_student"] or flags["is_parent"] or flags["is_teacher"] or flags["is_assistant"]) and flags["can_manage_all"]:
        products = _base_product_queryset()

    return _render_products_page(
        request,
        products,
        flags,
        page_title="Dự án của tôi",
        page_description="Các sản phẩm liên quan tới bạn, học sinh của bạn hoặc con của bạn.",
    )


@login_required
def student_product_detail(request, pk: int):
    product = get_object_or_404(
        StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
            "session__klass__center",
        ),
        pk=pk,
    )
    user = request.user
    flags = _product_role_flags(user)
    allowed = False

    if flags["is_student"] and product.student_id == user.id:
        allowed = True
    if flags["is_parent"]:
        child_ids = ParentStudentRelation.objects.filter(parent=user).values_list("student_id", flat=True)
        if product.student_id in child_ids:
            allowed = True
    if flags["is_teacher"] or flags["is_assistant"]:
        if (
            product.session.klass.main_teacher_id == user.id
            or product.session.klass.assistants.filter(id=user.id).exists()
            or product.session.teacher_override_id == user.id
            or product.session.assistants.filter(id=user.id).exists()
        ):
            allowed = True
    if flags["can_manage_all"]:
        allowed = True

    if not allowed:
        raise PermissionDenied("Bạn không có quyền xem sản phẩm này.")

    return render(
        request,
        "student_product_detail.html",
        {
            "product": product,
            "can_edit": product.student_id == user.id,
        },
    )


def student_product_detail_public(request, pk: int):
    product = get_object_or_404(
        StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
            "session__klass__center",
        ),
        pk=pk,
    )
    related_products = (
        StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
        )
        .filter(session__klass__subject=product.session.klass.subject)
        .exclude(pk=product.pk)
        .order_by("-created_at")[:5]
    )
    return render(
        request,
        "student_product_detail_public.html",
        {
            "product": product,
            "can_edit": False,
            "related_products": related_products,
        },
    )
