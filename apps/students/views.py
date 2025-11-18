from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Min
from django.shortcuts import get_object_or_404, render

from apps.enrollments.models import Enrollment
from apps.classes.models import Class
from apps.class_sessions.models import ClassSession


def _week_range(center_date: date | None = None):
    today = center_date or date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end


@login_required
def portal_home(request):
    """Student landing page: schedule + enrolled classes."""
    user = request.user

    # Schedule range (Mon-Sun of current week)
    start, end = _week_range()

    # Own or children schedule is out-of-scope here; show user's schedule
    sessions = (
        ClassSession.objects.filter(
            klass__enrollments__student=user, date__gte=start, date__lte=end
        )
        .select_related("klass", "klass__subject", "klass__center")
        .order_by("date", "start_time")
    )

    # Enrolled classes with next upcoming session
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
        class_cards.append({
            "klass": en.klass,
            "next_session": next_session,
        })

    context = {
        "sessions": sessions,
        "start": start,
        "end": end,
        "class_cards": class_cards,
    }
    return render(request, "student_home.html", context)


@login_required
def portal_course_detail(request, class_id: int):
    """Course detail: modules/lessons and next session info."""
    user = request.user
    klass = get_object_or_404(
        Class.objects.select_related("subject", "center", "main_teacher"), id=class_id
    )

    # Security: ensure the student is enrolled
    if not Enrollment.objects.filter(student=user, klass=klass, active=True).exists():
        # Fallback to a simple 403-like page inside template
        return render(request, "not_enrolled.html", {"klass": klass})

    # Upcoming session for this class
    upcoming = (
        ClassSession.objects.filter(klass=klass, date__gte=date.today())
        .select_related("lesson")
        .order_by("date", "start_time")
        .first()
    )

    # Curriculum tree
    subject = klass.subject
    modules = subject.modules.prefetch_related("lessons").all()

    context = {
        "klass": klass,
        "subject": subject,
        "modules": modules,
        "upcoming": upcoming,
    }
    return render(request, "course_detail.html", context)