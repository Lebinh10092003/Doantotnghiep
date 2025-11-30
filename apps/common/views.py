from datetime import date, timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

# Domain models
try:
    from apps.centers.models import Center, Room
except Exception:
    Center = None
    Room = None
try:
    from apps.classes.models import Class, CLASS_STATUS
except Exception:
    Class = None
    CLASS_STATUS = []
# Thêm import cho ClassSession
try:
    from apps.class_sessions.models import ClassSession, SESSION_STATUS
except Exception:
    ClassSession = None
    SESSION_STATUS = []
try:
    from apps.students.models import StudentProduct
except Exception:
    StudentProduct = None
try:
    from apps.parents.services import build_parent_children_snapshot
except Exception:
    build_parent_children_snapshot = None
try:
    from apps.enrollments.models import Enrollment, EnrollmentStatus
except Exception:
    Enrollment = None
    EnrollmentStatus = None
try:
    from apps.attendance.models import Attendance, ATTEND_CHOICES
except Exception:
    Attendance = None
    ATTEND_CHOICES = []


def _choices_to_dict(choices):
    if not choices:
        return {}
    return {value: label for value, label in choices}


def _month_start(base_date: date, months_back: int) -> date:
    year = base_date.year
    month = base_date.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)
   
def home(request):
    home_products = []
    home_page_obj = None
    home_paginator = None
    if StudentProduct:
        products_qs = StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
        ).order_by("-created_at")
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(products_qs, 3)
        page_number = request.GET.get("products_page", 1)
        try:
            home_page_obj = paginator.page(page_number)
        except EmptyPage:
            home_page_obj = paginator.page(1)
        home_paginator = paginator
        home_products = home_page_obj.object_list

    return render(
        request,
        "home.html",
        {
            "home_products": home_products,
            "home_page_obj": home_page_obj,
            "home_paginator": home_paginator,
        },
    )




@login_required
def dashboard(request):
    User = get_user_model()

    user = request.user
    role = getattr(user, "role", "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()

    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group("CENTER_MANAGER")
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_assistant = role == "ASSISTANT" or in_group("Assistant") or in_group("ASSISTANT")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")


    context = {"dashboard_role": "user"}
    today = date.today()

    if is_admin:
        admin_center_chart = []
        admin_chart_centers_has_data = False
        admin_enrollment_trend_chart = []
        admin_chart_enrollment_trend_has_data = False
        admin_enrollment_status_chart = []
        if Center and Class:
            centers_qs = list(
                Center.objects.annotate(
                    ongoing_classes=Count("classes", filter=Q(classes__status="ONGOING")),
                    active_students=Count(
                        "classes__enrollments",
                        filter=Q(classes__enrollments__active=True),
                        distinct=True,
                    ),
                )
                .order_by("name")
            )
            admin_chart_centers_has_data = bool(centers_qs)
            admin_center_chart = [
                {
                    "center": center.name,
                    "classes": center.ongoing_classes,
                    "students": center.active_students,
                }
                for center in centers_qs
            ]
        if Enrollment:
            six_months_ago = today - timedelta(days=180)
            enrollment_trend_qs = list(
                Enrollment.objects.filter(joined_at__gte=six_months_ago)
                .annotate(month=TruncMonth("joined_at"))
                .values("month")
                .annotate(count=Count("id"))
                .order_by("month")
            )
            admin_chart_enrollment_trend_has_data = bool(enrollment_trend_qs)
            trend_map = {}
            for row in enrollment_trend_qs:
                month_value = row.get("month")
                if month_value:
                    trend_map[month_value.strftime("%m/%Y")] = row["count"]
            for offset in range(5, -1, -1):
                month_label = _month_start(today, offset).strftime("%m/%Y")
                admin_enrollment_trend_chart.append(
                    {
                        "label": month_label,
                        "value": trend_map.get(month_label, 0),
                    }
                )
            status_label_map = _choices_to_dict(getattr(EnrollmentStatus, "choices", []))
            enrollment_status_qs = (
                Enrollment.objects.values("status").annotate(count=Count("id")).order_by("status")
            )
            status_count_map = {row["status"]: row["count"] for row in enrollment_status_qs}
            if status_label_map:
                admin_enrollment_status_chart = [
                    {
                        "label": label,
                        "value": status_count_map.get(value, 0),
                    }
                    for value, label in status_label_map.items()
                ]
            else:
                admin_enrollment_status_chart = [
                    {
                        "label": row["status"],
                        "value": row["count"],
                    }
                    for row in enrollment_status_qs
                ]
            if not admin_enrollment_status_chart:
                admin_enrollment_status_chart = [
                    {"label": "Chưa có dữ liệu", "value": 0}
                ]
        else:
            for offset in range(5, -1, -1):
                month_label = _month_start(today, offset).strftime("%m/%Y")
                admin_enrollment_trend_chart.append(
                    {
                        "label": month_label,
                        "value": 0,
                    }
                )
            admin_enrollment_status_chart = [
                {"label": "Chưa có dữ liệu", "value": 0}
            ]
        context.update(
            {
                "dashboard_role": "admin",
                "centers_count": Center.objects.count() if Center else None,
                "rooms_count": Room.objects.count() if Room else None,
                "users_count": User.objects.count(),
                "groups_count": Group.objects.count(),
                "classes_count": Class.objects.count() if Class else None,
                "admin_chart_centers": admin_center_chart,
                "admin_chart_centers_has_data": admin_chart_centers_has_data,
                "admin_chart_enrollment_trend": admin_enrollment_trend_chart,
                "admin_chart_enrollment_trend_has_data": admin_chart_enrollment_trend_has_data,
                "admin_chart_enrollment_status": admin_enrollment_status_chart,
            }
        )
    elif is_center_manager:
        center = getattr(user, "center", None)
        # Counts scoped to manager's center (if linked)
        if center and Center and Room:
            teachers_q = Q(role="TEACHER") | Q(groups__name__in=["Teacher", "TEACHER"])
            students_q = Q(role="STUDENT") | Q(groups__name__in=["Student", "STUDENT"]) 
            class_status_chart = []
            enrollment_status_chart = []
            attendance_status_chart = []
            if Class:
                status_label_map = _choices_to_dict(CLASS_STATUS)
                class_status_counts = (
                    Class.objects.filter(center=center)
                    .values("status")
                    .annotate(count=Count("id"))
                    .order_by("status")
                )
                class_status_chart = [
                    {
                        "label": status_label_map.get(row["status"], row["status"]),
                        "value": row["count"],
                    }
                    for row in class_status_counts
                ]
            if Enrollment:
                status_label_map = _choices_to_dict(getattr(EnrollmentStatus, "choices", []))
                enrollment_status_counts = (
                    Enrollment.objects.filter(klass__center=center)
                    .values("status")
                    .annotate(count=Count("id"))
                    .order_by("status")
                )
                enrollment_status_chart = [
                    {
                        "label": status_label_map.get(row["status"], row["status"]),
                        "value": row["count"],
                    }
                    for row in enrollment_status_counts
                ]
            if Attendance:
                attendance_label_map = _choices_to_dict(ATTEND_CHOICES)
                thirty_days_ago = today - timedelta(days=30)
                attendance_counts = (
                    Attendance.objects.filter(
                        session__klass__center=center, session__date__gte=thirty_days_ago
                    )
                    .values("status")
                    .annotate(count=Count("id"))
                    .order_by("status")
                )
                attendance_status_chart = [
                    {
                        "label": attendance_label_map.get(row["status"], row["status"]),
                        "value": row["count"],
                    }
                    for row in attendance_counts
                ]

            context.update(
                {
                    "dashboard_role": "center_manager",
                    "center": center,
                    "cm_users_count": User.objects.filter(center=center).distinct().count(),
                    "cm_rooms_count": Room.objects.filter(center=center).count(),
                    "cm_classes_count": (Class.objects.filter(center=center).count() if Class else None),
                    "cm_teachers_count": User.objects.filter(center=center).filter(teachers_q).distinct().count(),
                    "cm_students_count": User.objects.filter(center=center).filter(students_q).distinct().count(),
                    "center_class_status_chart": class_status_chart,
                    "center_enrollment_status_chart": enrollment_status_chart,
                    "center_attendance_status_chart": attendance_status_chart,
                }
            )
        else:
            context.update({"dashboard_role": "center_manager"})
    
    elif is_parent and build_parent_children_snapshot:
        snapshot = build_parent_children_snapshot(user)
        children_list = snapshot["children_data"]
        selected_child = children_list[0] if children_list else None
        selected_child_id = None
        child_param = request.GET.get("child")
        if child_param and children_list:
            try:
                child_param_id = int(child_param)
                for child in children_list:
                    student_obj = child.get("student")
                    if student_obj and student_obj.id == child_param_id:
                        selected_child = child
                        selected_child_id = child_param_id
                        break
            except (TypeError, ValueError):
                pass
        if selected_child and selected_child_id is None:
            student_obj = selected_child.get("student")
            if student_obj:
                selected_child_id = student_obj.id
        context.update(
            {
                "dashboard_role": "parent",
                "parent_summary_metrics": snapshot["summary_metrics"],
                "parent_recent_updates": snapshot["recent_updates"],
                "parent_children_cards": children_list[:4],
                "parent_children_all": children_list,
                "parent_has_children": snapshot["has_children"],
                "parent_child_names": snapshot.get("child_display_names", []),
                "parent_photo_feed": snapshot.get("recent_photo_feed", []),
                "parent_selected_child": selected_child,
                "parent_selected_child_id": selected_child_id,
            }
        )
    elif (is_teacher or is_assistant) and Class and ClassSession:
        teaching_scope_filter = (
            Q(klass__main_teacher=user)
            | Q(klass__assistants=user)
            | Q(teacher_override=user)
            | Q(assistants=user)
        )
        # Lấy các buổi dạy sắp tới (planned, từ hôm nay)
        upcoming_sessions_qs = ClassSession.objects.filter(
            teaching_scope_filter,
            date__gte=today,
            status="PLANNED"
        ).select_related('klass', 'lesson').order_by('date', 'start_time')
        
        # Lấy các lớp đang dạy (ongoing)
        teaching_classes_qs = Class.objects.filter(
            Q(main_teacher=user) | Q(assistants=user),
            status="ONGOING"
        ).distinct()

        week_end = today + timedelta(days=6)
        weekly_sessions_chart = []
        sessions_by_day = (
            ClassSession.objects.filter(teaching_scope_filter, date__gte=today, date__lte=week_end)
            .values("date")
            .annotate(count=Count("id"))
        )
        sessions_by_day_map = {row["date"]: row["count"] for row in sessions_by_day}
        for offset in range(7):
            day = today + timedelta(days=offset)
            weekly_sessions_chart.append(
                {
                    "label": day.strftime("%d/%m"),
                    "value": sessions_by_day_map.get(day, 0),
                }
            )

        session_status_chart = []
        status_label_map = _choices_to_dict(SESSION_STATUS)
        status_counts = (
            ClassSession.objects.filter(teaching_scope_filter, date__gte=today - timedelta(days=30))
            .values("status")
            .annotate(count=Count("id"))
        )
        session_status_chart = [
            {
                "label": status_label_map.get(row["status"], row["status"]),
                "value": row["count"],
            }
            for row in status_counts
        ]

        context.update({
            "dashboard_role": "teacher_assistant",
            "teaching_classes_count": teaching_classes_qs.count(),
            "upcoming_sessions_count": upcoming_sessions_qs.count(),
            "upcoming_sessions_list": upcoming_sessions_qs[:5], # Chỉ lấy 5 buổi gần nhất
            "teacher_weekly_sessions_chart": weekly_sessions_chart,
            "teacher_session_status_chart": session_status_chart,
        })


    return render(request, "dashboard/index.html", context)
