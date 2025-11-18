# apps/students/views.py
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.classes.models import Class
from apps.class_sessions.models import ClassSession
from apps.enrollments.models import Enrollment
from .models import StudentProduct
from django.core.exceptions import ObjectDoesNotExist



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
    if upcoming:
        session_products = (
            StudentProduct.objects.filter(session=upcoming, student=user)
            .select_related("session")
            .all()
        )
    else:
        session_products = StudentProduct.objects.none()

    # Tất cả sản phẩm của học sinh trong toàn bộ khóa (mọi buổi)
    my_products = (
        StudentProduct.objects.filter(student=user, session__klass=klass)
        .select_related("session")
        .order_by("-created_at")
    )

    context = {
        "klass": klass,
        "subject": subject,
        "modules": modules,
        "upcoming": upcoming,
        "lesson": lesson,
        "lecture": lecture,
        "exercise": exercise,
        "session_products": session_products,
        "my_products": my_products,
    }
    return render(request, "course_detail.html", context)