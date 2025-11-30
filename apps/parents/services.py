from collections import defaultdict
from datetime import date
from typing import Dict, List

from django.db.models import Avg, Count, Q

from apps.accounts.models import ParentStudentRelation
from apps.assessments.models import Assessment
from apps.attendance.models import Attendance
from apps.class_sessions.models import ClassSessionPhoto
from apps.enrollments.models import Enrollment


def build_parent_children_snapshot(parent) -> Dict[str, object]:
    """Aggregate learning overview data for a parent user."""
    relations = (
        ParentStudentRelation.objects.filter(parent=parent)
        .select_related("student", "student__center")
        .order_by("student__first_name", "student__last_name")
    )

    children_data: List[Dict[str, object]] = []
    summary_metrics = {
        "total_children": 0,
        "active_classes": 0,
        "attendance_rate": None,
        "total_absences": 0,
        "average_score": None,
    }
    recent_updates: List[Dict[str, object]] = []

    if relations:
        child_ids = [rel.student_id for rel in relations]

        enrollments_map = defaultdict(list)
        enrollments = (
            Enrollment.objects.filter(student_id__in=child_ids, active=True)
            .select_related("klass", "klass__center", "klass__subject")
            .order_by("student_id", "klass__name")
        )
        for enrollment in enrollments:
            enrollments_map[enrollment.student_id].append(enrollment)

        attendance_summary_map = {
            row["student_id"]: row
            for row in (
                Attendance.objects.filter(student_id__in=child_ids)
                .values("student_id")
                .annotate(
                    total=Count("id"),
                    present=Count("id", filter=Q(status="P")),
                    absent=Count("id", filter=Q(status="A")),
                    late=Count("id", filter=Q(status="L")),
                )
            )
        }

        latest_attendance_map = {}
        latest_attendance_qs = (
            Attendance.objects.filter(student_id__in=child_ids)
            .select_related("session", "session__klass", "session__klass__center")
            .order_by("student_id", "-session__date", "-session__start_time", "-session_id")
        )
        for att in latest_attendance_qs:
            if att.student_id not in latest_attendance_map:
                latest_attendance_map[att.student_id] = att

        avg_score_map = {
            row["student_id"]: row["avg_score"]
            for row in (
                Assessment.objects.filter(student_id__in=child_ids, score__isnull=False)
                .values("student_id")
                .annotate(avg_score=Avg("score"))
            )
        }

        recent_photos_map = defaultdict(list)
        for student_id in child_ids:
            photos = (
                ClassSessionPhoto.objects.filter(
                    session__klass__enrollments__student_id=student_id,
                    session__klass__enrollments__active=True,
                )
                .select_related("session", "session__klass", "session__klass__center", "uploaded_by")
                .order_by("-created_at")[:4]
            )
            recent_photos_map[student_id] = list(photos)

        present_total = 0
        attendance_total = 0
        score_values = []
        for rel in relations:
            sid = rel.student_id
            attendance_summary = attendance_summary_map.get(sid)
            latest_attendance = latest_attendance_map.get(sid)
            avg_score = avg_score_map.get(sid)
            enrollments_list = enrollments_map.get(sid, [])
            children_data.append(
                {
                    "student": rel.student,
                    "note": rel.note,
                    "enrollments": enrollments_list,
                    "attendance_summary": attendance_summary,
                    "latest_attendance": latest_attendance,
                    "avg_score": avg_score,
                    "recent_photos": recent_photos_map.get(sid, []),
                }
            )
            summary_metrics["active_classes"] += len(enrollments_list)
            if attendance_summary:
                present_total += attendance_summary.get("present", 0)
                attendance_total += attendance_summary.get("total", 0)
                summary_metrics["total_absences"] += attendance_summary.get("absent", 0)
            if avg_score is not None:
                score_values.append(avg_score)
            if latest_attendance:
                recent_updates.append(
                    {
                        "student": rel.student,
                        "klass": latest_attendance.session.klass,
                        "status": latest_attendance.status,
                        "status_label": latest_attendance.get_status_display(),
                        "date": latest_attendance.session.date,
                        "note": latest_attendance.note,
                    }
                )

        if attendance_total:
            summary_metrics["attendance_rate"] = round((present_total / attendance_total) * 100, 1)
        if score_values:
            summary_metrics["average_score"] = round(sum(score_values) / len(score_values), 1)
        recent_updates.sort(key=lambda item: item.get("date") or date.min, reverse=True)
        recent_updates = recent_updates[:5]

    summary_metrics["total_children"] = len(children_data)
    return {
        "relations": relations,
        "children_data": children_data,
        "summary_metrics": summary_metrics,
        "recent_updates": recent_updates,
        "has_children": bool(children_data),
    }
