from collections import defaultdict

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

# Import các mô hình cần thiết, sử dụng try-except để tránh lỗi khi mô hình không tồn tại
try:
    from apps.class_sessions.models import ClassSession
except Exception:
    ClassSession = None
try:
    from apps.students.models import StudentProduct
except Exception:
    StudentProduct = None
try:
    from apps.parents.services import build_parent_children_snapshot
except Exception:
    build_parent_children_snapshot = None
try:
    from apps.enrollments.models import Enrollment
except Exception:
    Enrollment = None
try:
    from apps.attendance.models import Attendance
except Exception:
    Attendance = None

# Các hàm phụ để sử dụng trong dashboard
def _choices_to_dict(choices):
    if not choices:
        return {}
    return {value: label for value, label in choices}

# Hàm phụ để hiển thị tên người dùng
def _user_display(user):
    if not user:
        return ""
    full_name = getattr(user, "get_full_name", None)
    if callable(full_name):
        name = full_name()
        if name:
            return name
    return getattr(user, "username", "")

# Hàm phụ để xác định trạng thái buổi học
def _session_state_label(session, current_time):
    start = getattr(session, "start_time", None)
    end = getattr(session, "end_time", None)
    if start and end:
        if end < current_time:
            return ("Đã kết thúc", "success")
        if start <= current_time <= end:
            return ("Đang diễn ra", "info")
        if start > current_time:
            return ("Chưa bắt đầu", "secondary")
    if start and not end:
        if start <= current_time:
            return ("Đang diễn ra", "info")
        return ("Chưa bắt đầu", "secondary")
    return ("Chưa xếp giờ", "light")

# Hàm phụ để định dạng khoảng thời gian
def _format_time_range(start, end):
    if start and end:
        return f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
    if start:
        return start.strftime("%H:%M")
    return "Chưa xếp giờ"

# Hàm phụ để xác định trạng thái điểm danh
def _attendance_state(summary, session, current_time):
    if summary and summary.get("total"):
        return ("Đã điểm danh", "success")
    state_label, state_badge = _session_state_label(session, current_time)
    if state_label == "Đã kết thúc":
        return ("Chưa điểm danh", "warning")
    return (state_label, state_badge)

# Hàm phụ để tính tỷ lệ và phần trăm
def _ratio_text(current_value, total_value):
    if total_value:
        percent = round((current_value / total_value) * 100)
        percent = max(0, min(percent, 100))
        return f"{current_value}/{total_value}", percent
    return (f"{current_value}/—", None)

# Hàm phụ để tổng hợp điểm danh theo buổi học
def _attendance_totals_by_session(session_ids):
    if not Attendance or not session_ids:
        return {}
    summary = defaultdict(lambda: {"present": 0, "absent": 0, "late": 0, "total": 0})
    rows = (
        Attendance.objects.filter(session_id__in=session_ids)
        .values("session_id", "status")
        .annotate(count=Count("id"))
    )
    for row in rows:
        entry = summary[row["session_id"]]
        entry["total"] += row["count"]
        status = row["status"]
        if status == "P":
            entry["present"] += row["count"]
        elif status == "A":
            entry["absent"] += row["count"]
        elif status == "L":
            entry["late"] += row["count"]
    return summary

# Hàm phụ để lấy bản đồ điểm danh cho học sinh trong ngày
def _attendance_map_for_students(student_ids, date_value):
    if not Attendance or not student_ids:
        return {}
    result = {}
    qs = Attendance.objects.filter(session__date=date_value, student_id__in=student_ids).select_related("session")
    for attendance in qs:
        result[(attendance.session_id, attendance.student_id)] = attendance
    return result

# Trang chủ chung của ứng dụng
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

# Trang dashboard tùy theo vai trò người dùng
@login_required
def dashboard(request):
    user = request.user
    role = getattr(user, "role", "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()

    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group("CENTER_MANAGER")
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_assistant = role == "ASSISTANT" or in_group("Assistant") or in_group("ASSISTANT")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")
    is_student = role == "STUDENT" or in_group("Student") or in_group("STUDENT")

    context = {
        "dashboard_role": "user",
        "today": timezone.localdate(),
    }
    today = context["today"]
    now = timezone.localtime()
    now_time = now.time()

    if not ClassSession:
        context.update(
            {
                "dashboard_role": "generic",
                "generic_message": "Chức năng dashboard chưa khả dụng.",
            }
        )
        return render(request, "dashboard/index.html", context)

    if is_admin and ClassSession:
        sessions_today = ClassSession.objects.filter(date=today)
        total_sessions_today = sessions_today.count()
        centers_activity = []
        active_centers_count = 0
        total_expected_students = 0
        active_classes_today = sessions_today.values("klass_id").distinct().count()
        if total_sessions_today:
            center_rows = list(
                sessions_today
                .values("klass__center__name")
                .annotate(
                    total_sessions=Count("id", distinct=True),
                    expected_students=Count(
                        "klass__enrollments__student",
                        filter=Q(klass__enrollments__active=True),
                        distinct=True,
                    ),
                    active_classes=Count("klass", distinct=True),
                )
                .order_by("klass__center__name")
            )
            active_centers_count = len(center_rows)
            total_expected_students = sum(row.get("expected_students", 0) or 0 for row in center_rows)
            for row in center_rows:
                centers_activity.append(
                    {
                        "center": row["klass__center__name"] or "Chưa phân bổ",
                        "sessions": row["total_sessions"],
                        "classes": row["active_classes"],
                        "students": row["expected_students"],
                    }
                )

        admin_cards = [
            {
                "label": "Học sinh tham gia",
                "value": total_expected_students,
                "icon": "bi-people",
                "accent": "primary",
                "subtitle": "Theo lịch hôm nay",
            },
            {
                "label": "Trung tâm hoạt động",
                "value": active_centers_count,
                "icon": "bi-building",
                "accent": "info",
                "subtitle": "Có lớp diễn ra",
            },
            {
                "label": "Lớp hoạt động",
                "value": active_classes_today,
                "icon": "bi-collection",
                "accent": "success",
                "subtitle": "Trong ngày",
            },
            {
                "label": "Buổi diễn ra",
                "value": total_sessions_today,
                "icon": "bi-calendar-week",
                "accent": "warning",
                "subtitle": "Toàn hệ thống",
            },
        ]

        context.update(
            {
                "dashboard_role": "admin",
                "admin_cards": admin_cards,
                "admin_centers_activity": centers_activity,
            }
        )

    elif is_center_manager and ClassSession:
        center = getattr(user, "center", None)
        if center:
            sessions_today = (
                ClassSession.objects.filter(date=today, klass__center=center)
                .select_related(
                    "klass",
                    "klass__main_teacher",
                    "klass__room",
                    "room_override",
                )
                .annotate(
                    expected_students=Count(
                        "klass__enrollments__student",
                        filter=Q(klass__enrollments__active=True),
                        distinct=True,
                    )
                )
                .order_by("start_time", "klass__name")
            )
            sessions_today = list(sessions_today)
            session_ids = [session.id for session in sessions_today]
            attendance_summary = _attendance_totals_by_session(session_ids)
            students_present = sum(item.get("present", 0) for item in attendance_summary.values())
            sessions_without_attendance = sum(
                1
                for session in sessions_today
                if not attendance_summary.get(session.id, {}).get("total")
            )

            cm_cards = [
                {
                    "label": "Buổi học hôm nay",
                    "value": len(sessions_today),
                    "icon": "bi-mortarboard",
                    "accent": "primary",
                    "subtitle": center.name or "Trung tâm",
                },
                {
                    "label": "Học viên có mặt",
                    "value": students_present,
                    "icon": "bi-people",
                    "accent": "success",
                    "subtitle": "Đã check-in",
                },
                {
                    "label": "Buổi chưa điểm danh",
                    "value": sessions_without_attendance,
                    "icon": "bi-exclamation-triangle",
                    "accent": "danger",
                    "subtitle": "Cần xử lý",
                },
            ]

            schedule_rows = []
            for session in sessions_today:
                summary = attendance_summary.get(session.id, {})
                present = summary.get("present", 0)
                expected = session.expected_students or 0
                ratio_text, ratio_percent = _ratio_text(present, expected)
                teacher = session.teacher_override or getattr(session.klass, "main_teacher", None)
                room = session.room_override or getattr(session.klass, "room", None)
                attendance_label, attendance_badge = _attendance_state(summary, session, now_time)
                schedule_rows.append(
                    {
                        "time_label": _format_time_range(session.start_time, session.end_time),
                        "class_name": session.klass.name if session.klass else "—",
                        "room_name": room.name if room else "Chưa xếp phòng",
                        "teacher_name": _user_display(teacher) or "Chưa phân công",
                        "attendance_label": attendance_label,
                        "attendance_badge": attendance_badge,
                        "attendance_ratio_text": ratio_text,
                        "attendance_ratio_percent": ratio_percent,
                    }
                )

            context.update(
                {
                    "dashboard_role": "center_manager",
                    "cm_center": center,
                    "cm_cards": cm_cards,
                    "cm_schedule": schedule_rows,
                }
            )
        else:
            context.update(
                {
                    "dashboard_role": "generic",
                    "generic_message": "Tài khoản chưa được gán trung tâm.",
                }
            )

    elif (is_teacher or is_assistant) and ClassSession:
        teaching_filter = (
            Q(klass__main_teacher=user)
            | Q(assistants=user)
            | Q(teacher_override=user)
        )
        sessions_queryset = (
            ClassSession.objects.filter(date=today)
            .filter(teaching_filter)
            .select_related(
                "klass",
                "klass__center",
                "klass__room",
                "room_override",
            )
            .annotate(
                expected_students=Count(
                    "klass__enrollments__student",
                    filter=Q(klass__enrollments__active=True),
                    distinct=True,
                )
            )
            .order_by("start_time", "klass__name")
            .distinct()
        )
        sessions_today = list(sessions_queryset)
        session_ids = [session.id for session in sessions_today]
        attendance_summary = _attendance_totals_by_session(session_ids)
        total_sessions = len(session_ids)
        attended_sessions = sum(
            1 for session_id in session_ids if attendance_summary.get(session_id, {}).get("total")
        )
        pending_sessions = max(total_sessions - attended_sessions, 0)

        teacher_cards = [
            {
                "label": "Buổi dạy hôm nay",
                "value": total_sessions,
                "icon": "bi-calendar-day",
                "accent": "primary",
                "subtitle": "Lịch trong ngày",
            },
            {
                "label": "Đã điểm danh",
                "value": attended_sessions,
                "icon": "bi-clipboard-check",
                "accent": "success",
                "subtitle": "Hoàn tất",
            },
            {
                "label": "Chưa điểm danh",
                "value": pending_sessions,
                "icon": "bi-hourglass-split",
                "accent": "warning",
                "subtitle": "Cần xử lý",
            },
        ]

        schedule_rows = []
        for session in sessions_today:
            summary = attendance_summary.get(session.id, {})
            room = session.room_override or getattr(session.klass, "room", None)
            attendance_label, attendance_badge = _attendance_state(summary, session, now_time)
            present = summary.get("present", 0)
            expected = session.expected_students or 0
            ratio_text, ratio_percent = _ratio_text(present, expected)
            schedule_rows.append(
                {
                    "time_label": _format_time_range(session.start_time, session.end_time),
                    "class_name": session.klass.name if session.klass else "—",
                    "expected": session.expected_students,
                    "status_label": attendance_label,
                    "status_badge": attendance_badge,
                    "room_name": room.name if room else "Chưa xếp phòng",
                    "action_url": reverse("class_sessions:session_detail", args=[session.id]),
                    "attendance_ratio_text": ratio_text,
                    "attendance_ratio_percent": ratio_percent,
                    "center_name": session.klass.center.name if session.klass and session.klass.center else "—",
                }
            )

        context.update(
            {
                "dashboard_role": "teacher_assistant",
                "teacher_cards": teacher_cards,
                "teacher_schedule": schedule_rows,
            }
        )

    elif is_parent and build_parent_children_snapshot and ClassSession:
        snapshot = build_parent_children_snapshot(user)
        children_entries = []
        child_ids = []
        for child in snapshot.get("children_data", []):
            student = child.get("student")
            if not student:
                continue
            label = child.get("student_label") or _user_display(student)
            children_entries.append({"student": student, "label": label})
            child_ids.append(student.id)

        attendance_map = _attendance_map_for_students(child_ids, today) if child_ids else {}

        total_sessions = 0
        children_with_schedule = 0
        parent_schedule_rows = []

        for entry in children_entries:
            student = entry["student"]
            sessions = (
                ClassSession.objects.filter(
                    date=today,
                    klass__enrollments__student=student,
                    klass__enrollments__active=True,
                )
                .select_related("klass", "klass__center", "klass__room", "room_override")
                .order_by("start_time", "klass__name")
                .distinct()
            )
            sessions = list(sessions)
            if sessions:
                children_with_schedule += 1
            total_sessions += len(sessions)
            for session in sessions:
                attendance = attendance_map.get((session.id, student.id))
                if attendance:
                    status_label = attendance.get_status_display()
                    status_badge = "success" if attendance.status == "P" else "danger"
                else:
                    status_label, status_badge = _attendance_state({}, session, now_time)
                room = session.room_override or getattr(session.klass, "room", None)
                parent_schedule_rows.append(
                    {
                        "child_label": entry["label"],
                        "time_label": _format_time_range(session.start_time, session.end_time),
                        "class_name": session.klass.name if session.klass else "—",
                        "center_name": session.klass.center.name if session.klass and session.klass.center else "—",
                        "room_name": room.name if room else "Chưa xếp phòng",
                        "status_label": status_label,
                        "status_badge": status_badge,
                    }
                )

        parent_cards = [
            {
                "label": "Số con có lịch hôm nay",
                "value": children_with_schedule,
                "icon": "bi-people",
                "accent": "info",
                "subtitle": "Có lịch học",
            },
            {
                "label": "Số buổi học hôm nay",
                "value": total_sessions,
                "icon": "bi-calendar-event",
                "accent": "primary",
                "subtitle": "Tất cả các con",
            },
        ]

        context.update(
            {
                "dashboard_role": "parent",
                "parent_cards": parent_cards,
                "parent_schedule": parent_schedule_rows,
            }
        )

    elif is_student and ClassSession:
        sessions_today = (
            ClassSession.objects.filter(
                date=today,
                klass__enrollments__student=user,
                klass__enrollments__active=True,
            )
            .select_related("klass", "klass__center", "klass__room", "room_override")
            .order_by("start_time", "klass__name")
            .distinct()
        )
        session_ids = list(sessions_today.values_list("id", flat=True))
        attendance_map = _attendance_map_for_students([user.id], today)
        assignments_due_today = 0

        student_cards = [
            {
                "label": "Số buổi học hôm nay",
                "value": len(session_ids),
                "icon": "bi-journal-bookmark",
                "accent": "primary",
                "subtitle": "Theo lịch",
            },
            {
                "label": "Bài tập đến hạn",
                "value": assignments_due_today,
                "icon": "bi-check2-square",
                "accent": "warning",
                "subtitle": "Trong ngày",
            },
        ]

        student_schedule = []
        for session in sessions_today:
            attendance = attendance_map.get((session.id, user.id))
            if attendance:
                status_label = attendance.get_status_display()
                status_badge = "success" if attendance.status == "P" else "danger"
            else:
                status_label, status_badge = _attendance_state({}, session, now_time)
            room = session.room_override or getattr(session.klass, "room", None)
            student_schedule.append(
                {
                    "time_label": _format_time_range(session.start_time, session.end_time),
                    "class_name": session.klass.name if session.klass else "—",
                    "room_name": room.name if room else "Chưa xếp phòng",
                    "center_name": session.klass.center.name if session.klass and session.klass.center else "—",
                    "status_label": status_label,
                    "status_badge": status_badge,
                }
            )

        context.update(
            {
                "dashboard_role": "student",
                "student_cards": student_cards,
                "student_schedule": student_schedule,
            }
        )

    else:
        context.update(
            {
                "dashboard_role": "generic",
                "generic_message": "Hiện chưa có dashboard cho vai trò này.",
            }
        )

    return render(request, "dashboard/index.html", context)
