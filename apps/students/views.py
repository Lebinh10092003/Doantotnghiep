# apps/students/views.py
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseForbidden

from apps.classes.models import Class
from apps.class_sessions.models import ClassSession
from apps.enrollments.models import Enrollment
from .models import StudentProduct, StudentExerciseSubmission
from .forms import StudentProductForm, StudentExerciseSubmissionForm
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
import json
from django.http import HttpResponse
from django.urls import reverse





def _week_range(center_date: date | None = None):
    """
    Trả về (start, end) là thứ 2 -> CN của tuần chứa center_date.
    """
    today = center_date or date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end


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
    session = get_object_or_404(ClassSession, id=session_id)
    if not Enrollment.objects.filter(student=request.user, klass=session.klass, active=True).exists():
        return HttpResponseForbidden("Bạn không có quyền đăng sản phẩm cho lớp này.")
    existing_product = StudentProduct.objects.filter(session=session, student=request.user).first()
    if existing_product:
        return redirect("students:product_update", pk=existing_product.pk)

    if request.method == "POST":
        form = StudentProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.session = session
            product.student = request.user
            product.save()
            return redirect("students:portal_course_detail", class_id=session.klass.id)
    else:
        form = StudentProductForm()

    return render(
        request,
        "student_product_form.html",
        {
            "form": form,
            "session": session,
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

    if request.method == "POST":
        form = StudentProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            new_file = form.cleaned_data.get("file")
            old_file = product.file
            form.save()
            if new_file and old_file and old_file.name != new_file.name:
                old_file.delete(save=False)
            return redirect("students:portal_course_detail", class_id=product.session.klass.id)
    else:
        form = StudentProductForm(instance=product)

    return render(
        request,
        "student_product_form.html",
        {
            "form": form,
            "session": product.session,
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
    is_student = user.groups.filter(name="student").exists()

    if not is_student and not user.has_perm("students.view_studentproduct"):
        raise PermissionDenied("Bạn không có quyền xem danh sách sản phẩm.")

    q = request.GET.get("q", "")
    klass_id = request.GET.get("klass_id")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    order = request.GET.get("order", "desc")

    products = (
        StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
            "session__klass__center",
        )
    )

    if is_student:
        products = products.filter(student=user)

    if q:
        products = products.filter(title__icontains=q)

    if klass_id:
        products = products.filter(session__klass_id=klass_id)

    if start_date:
        products = products.filter(session__date__gte=start_date)

    if end_date:
        products = products.filter(session__date__lte=end_date)

    sort_field = "created_at" if order == "asc" else "-created_at"
    products = products.order_by(sort_field)

    klasses = Class.objects.order_by("name")

    return render(
        request,
        "student_products_list.html",
        {
            "products": products,
            "is_student": is_student,
            "can_view_all": not is_student,
            "filter_params": {
                "q": q,
                "klass_id": klass_id,
                "start_date": start_date,
                "end_date": end_date,
                "order": order,
            },
            "klasses": klasses,
        },
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
    is_student = user.groups.filter(name="student").exists()
    if is_student:
        if product.student_id != user.id:
            raise PermissionDenied("Bạn không có quyền xem sản phẩm này.")
    else:
        if not user.has_perm("students.view_studentproduct"):
            raise PermissionDenied("Bạn không có quyền xem sản phẩm này.")

    return render(
        request,
        "student_product_detail.html",
        {
            "product": product,
            "can_edit": product.student_id == user.id,
        },
    )
