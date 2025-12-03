from datetime import date, datetime, timedelta
import csv
import re
from math import ceil
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.accounts.models import ParentStudentRelation, User
from apps.assessments.models import Assessment
from apps.attendance.models import Attendance
from apps.class_sessions.models import ClassSession, ClassSessionPhoto
from apps.class_sessions.forms import ClassSessionPhotoForm
from apps.classes.models import Class
from apps.centers.models import Center
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.students.models import StudentProduct, StudentExerciseSubmission
from apps.billing.models import BillingEntry
from apps.filters.models import SavedFilter
from apps.filters.utils import build_filter_badges, determine_active_filter_name
from apps.reports.filters import (
    ClassActivityReportFilter,
    EnrollmentSummaryFilter,
    RevenueReportFilter,
    StudentReportFilter,
    TeachingHoursReportFilter,
)
from apps.common.utils.http import is_htmx_request


def _normalize_identifier(value) -> str:
    if not value:
        return ""
    if hasattr(value, "name"):
        value = value.name
    return re.sub(r"\s+", "_", str(value)).strip().upper()


def _role_flags(user):
    normalized_role = _normalize_identifier(getattr(user, "role", ""))
    group_names = {_normalize_identifier(name) for name in user.groups.values_list("name", flat=True)}
    is_admin = bool(user.is_superuser or normalized_role == "ADMIN" or "ADMIN" in group_names)
    is_center_manager = bool(normalized_role == "CENTER_MANAGER" or "CENTER_MANAGER" in group_names)
    is_teacher = bool(normalized_role == "TEACHER" or "TEACHER" in group_names)
    is_assistant = bool(normalized_role == "ASSISTANT" or "ASSISTANT" in group_names)
    is_parent = bool(normalized_role == "PARENT" or "PARENT" in group_names)
    is_student = bool(normalized_role == "STUDENT" or "STUDENT" in group_names)
    return {
        "is_admin": is_admin,
        "is_center_manager": is_center_manager,
        "is_teacher": is_teacher,
        "is_assistant": is_assistant,
        "is_parent": is_parent,
        "is_student": is_student,
    }


def _user_is_admin_or_center_manager(user):
    flags = _role_flags(user)
    return flags["is_admin"], flags["is_center_manager"]


def _session_duration_hours(session):
    """
    Return duration in hours if start/end time are present; otherwise fallback to 0.
    """
    if session.start_time and session.end_time:
        start_dt = datetime.combine(session.date or date.today(), session.start_time)
        end_dt = datetime.combine(session.date or date.today(), session.end_time)
        delta = end_dt - start_dt
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        return round(delta.total_seconds() / 3600, 2)
    return 0


def _parse_date_safe(value: str | None) -> date | None:
    if not value:
        return None
    return parse_date(value)


def _build_student_report_context(request, *, paginate=False) -> dict:
    base_enrollments = _student_report_accessible_enrollments(request.user)
    flags = _role_flags(request.user)
    
    # Kiểm tra xem có bộ lọc nào được áp dụng không
    has_active_filters = False
    for key in request.GET.keys():
        if key not in {"page", "per_page", "detail"}:
            value = request.GET.get(key, "").strip()
            if value:
                has_active_filters = True
                break
    
    # Tạo filterset - nếu không có bộ lọc, chuyển data=None để tránh áp dụng mặc định
    filter_data = request.GET if has_active_filters else None
    filterset = StudentReportFilter(
        data=filter_data,
        queryset=base_enrollments,
        request=request,
    )
    enrollments = filterset.qs.select_related(
        "student",
        "klass__center",
        "klass__subject",
        "klass__main_teacher",
    ).order_by("student__last_name", "student__first_name", "student__username")
    
    start_date = _parse_date_safe(request.GET.get("start_date")) if has_active_filters else None
    end_date = _parse_date_safe(request.GET.get("end_date")) if has_active_filters else None

    if not has_active_filters and base_enrollments.exists():
        enrollments = base_enrollments.select_related(
            "student",
            "klass__center",
            "klass__subject",
            "klass__main_teacher",
        ).order_by("student__last_name", "student__first_name", "student__username")

    per_page_default = 10
    try:
        per_page = int(request.GET.get("per_page", per_page_default))
    except (TypeError, ValueError):
        per_page = per_page_default

    page_number = request.GET.get("page") or 1
    if paginate:
        paginator = Paginator(enrollments, per_page)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(1)
        enrollments_page = page_obj.object_list
    else:
        paginator = None
        page_obj = None
        enrollments_page = enrollments

    rows = _student_report_rows(
        enrollments_page,
        start_date=start_date,
        end_date=end_date,
    )

    center_ids = base_enrollments.values_list("klass__center_id", flat=True).distinct()
    centers = Center.objects.filter(id__in=center_ids).order_by("name")
    class_ids = base_enrollments.values_list("klass_id", flat=True).distinct()
    classes = (
        Class.objects.filter(id__in=class_ids)
        .select_related("center", "subject", "main_teacher")
        .order_by("name")
    )
    students = (
        base_enrollments.values(
            "student_id",
            "student__first_name",
            "student__last_name",
            "student__username",
        )
        .distinct()
        .order_by("student__last_name", "student__first_name")
    )

    filter_badges = []
    if filterset.form.is_bound:
        for name, value in filterset.form.cleaned_data.items():
            if not value or name not in filterset.form.fields:
                continue
            label = filterset.form.fields[name].label or name
            if hasattr(value, "get_full_name"):
                display = value.get_full_name() or str(value)
            else:
                display = getattr(value, "name", None) or str(value)
            filter_badges.append({"key": name, "label": label, "value": display})
    if start_date and not any(b["key"] == "start_date" for b in filter_badges):
        filter_badges.append(
            {"key": "start_date", "label": "Từ ngày", "value": start_date.strftime("%d/%m/%Y")}
        )
    if end_date and not any(b["key"] == "end_date" for b in filter_badges):
        filter_badges.append(
            {"key": "end_date", "label": "Đến ngày", "value": end_date.strftime("%d/%m/%Y")}
        )

    query_params_no_page = request.GET.copy()
    for key in ["page", "per_page", "detail"]:
        query_params_no_page.pop(key, None)
    current_query_params = query_params_no_page.urlencode()

    pdf_query = request.GET.copy()
    for key in ["page", "per_page", "detail"]:
        pdf_query.pop(key, None)
    pdf_query_string = pdf_query.urlencode()
    pdf_url = reverse("reports:student_report_pdf")
    if pdf_query_string:
        pdf_url = f"{pdf_url}?{pdf_query_string}"

    context = {
        "rows": rows,
        "centers": centers,
        "classes": classes,
        "students": students,
        "filter_params": {
            "center": request.GET.get("center") or "",
            "klass": request.GET.get("klass") or "",
            "student": request.GET.get("student") or "",
            "start_date": request.GET.get("start_date") or "",
            "end_date": request.GET.get("end_date") or "",
        },
        "filter_badges": filter_badges,
        "pdf_url": pdf_url,
        "paginator": paginator,
        "page_obj": page_obj,
        "per_page": per_page if paginate else None,
        "current_query_params": current_query_params,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="StudentReport",
        )
    )
    context.setdefault("detail_url_name", "reports:student_report_detail")
    return context


def _student_report_accessible_enrollments(user):
    flags = _role_flags(user)
    base = Enrollment.objects.select_related(
        "student", "klass__center", "klass__subject", "klass__main_teacher"
    )
    if flags["is_admin"]:
        return base
    if flags["is_center_manager"]:
        if not user.center:
            return Enrollment.objects.none()
        return base.filter(klass__center=user.center)
    if flags["is_teacher"]:
        taught = base.filter(
            Q(klass__main_teacher=user)
            | Q(klass__assistants=user)
            | Q(klass__sessions__teacher_override=user)
            | Q(klass__sessions__assistants=user)
        )
        return taught.distinct()
    if flags["is_parent"]:
        child_ids = ParentStudentRelation.objects.filter(parent=user).values_list("student_id", flat=True)
        return base.filter(student_id__in=child_ids)
    if flags["is_student"]:
        return base.filter(student=user)
    raise PermissionDenied


def _attendance_counts(student_id, session_ids):
    stats = {"P": 0, "A": 0, "L": 0}
    if not session_ids:
        return stats
    qs = Attendance.objects.filter(student_id=student_id, session_id__in=session_ids)
    rows = qs.values("status").annotate(total=Count("status"))
    for row in rows:
        stats[row["status"]] = row["total"]
    return stats


def _student_report_rows(enrollments, start_date=None, end_date=None):
    rows = []
    for enrollment in enrollments:
        sessions = ClassSession.objects.filter(klass=enrollment.klass)
        if start_date:
            sessions = sessions.filter(date__gte=start_date)
        if end_date:
            sessions = sessions.filter(date__lte=end_date)
        module_size = getattr(enrollment, "module_size", None) or 12
        session_ids = list(sessions.values_list("id", flat=True))
        total_sessions = sessions.count()
        # Tính hoàn thành gồm cả DONE và MISSED để tiến độ phản ánh buổi đã diễn ra.
        completed_sessions = sessions.filter(status__in=["DONE", "MISSED"]).count()
        attendance = _attendance_counts(enrollment.student_id, session_ids)
        missed_sessions = attendance.get("A", 0)
        sessions_total_from_fee = getattr(enrollment, "sessions_total", 0) or total_sessions
        # Hiển thị % dựa trên tổng buổi thực tế (theo bộ lọc) để tránh sai lệch khi học phí khai báo khác
        progress_denominator = total_sessions or sessions_total_from_fee
        progress_percent = int((completed_sessions / progress_denominator) * 100) if progress_denominator else 0
        assessments_qs = Assessment.objects.filter(student=enrollment.student, session_id__in=session_ids).select_related(
            "session"
        )
        assessments = assessments_qs.order_by("-session__date", "-session__index")[:3]
        assessments_by_session = {a.session_id: a for a in assessments_qs}
        products_qs = StudentProduct.objects.filter(student=enrollment.student, session_id__in=session_ids).select_related(
            "session"
        )
        products = products_qs.order_by("-created_at")[:3]
        products_by_session = {}
        for product in products_qs:
            products_by_session.setdefault(product.session_id, []).append(product)
        photos_qs = ClassSessionPhoto.objects.filter(session_id__in=session_ids).select_related("session")
        session_photos = photos_qs.order_by("-created_at")
        photos_by_session = {}
        for photo in photos_qs:
            photos_by_session.setdefault(photo.session_id, []).append(photo)
        attendance_by_session = {
            item["session_id"]: item["status"]
            for item in Attendance.objects.filter(student=enrollment.student, session_id__in=session_ids).values(
                "session_id", "status"
            )
        }
        sessions_detail = []
        for s in sessions.order_by("date", "index"):
            sessions_detail.append(
                {
                    "id": s.id,
                    "index": s.index,
                    "date": s.date,
                    "status": s.status,
                    "status_label": s.get_status_display(),
                    "attendance": attendance_by_session.get(s.id, "-"),
                    "assessment": assessments_by_session.get(s.id),
                    "products": products_by_session.get(s.id, []),
                    "photos": photos_by_session.get(s.id, []),
                    "module_number": ceil(s.index / module_size) if module_size else 1,
                }
            )
        # Xác định học phần đang học / đã học / chưa học dựa trên buổi sắp tới
        done_statuses = {"DONE", "MISSED"}
        upcoming_session = next((s for s in sessions_detail if s["status"] not in done_statuses), None)
        upcoming_module = upcoming_session["module_number"] if upcoming_session else None
        modules_meta = []
        for module_number in sorted({s["module_number"] for s in sessions_detail}):
            module_sessions = [s for s in sessions_detail if s["module_number"] == module_number]
            if upcoming_module is None:
                module_status = "Hoàn thành"
            elif module_number < upcoming_module:
                module_status = "Hoàn thành"
            elif module_number == upcoming_module:
                module_status = "Đang học"
            else:
                module_status = "Chưa học"
            modules_meta.append(
                {
                    "module_number": module_number,
                    "status": module_status,
                    "status_class": {
                        "Hoàn thành": "success",
                        "Đang học": "warning",
                        "Chưa học": "secondary",
                    }.get(module_status, "secondary"),
                    "sessions": module_sessions,
                    "total_sessions": len(module_sessions),
                }
            )
        parent_names = list(
            ParentStudentRelation.objects.filter(student=enrollment.student)
            .select_related("parent")
            .values_list("parent__first_name", "parent__last_name")
        )
        rows.append(
            {
                "enrollment": enrollment,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "missed_sessions": missed_sessions,
                "attendance": attendance,
                "progress_percent": progress_percent,
                "assessments": assessments,
                "products": products,
                "session_photos": session_photos,
                "parent_names": parent_names,
                "sessions_detail": sessions_detail,
                "modules": modules_meta,
                "sessions_total_from_fee": sessions_total_from_fee,
                "sessions_remaining": getattr(enrollment, "sessions_remaining", None)
                if getattr(enrollment, "sessions_remaining", None) is not None
                else max(sessions_total_from_fee - completed_sessions, 0),
            }
        )

    return rows


@login_required
def enrollment_summary(request):
    user = request.user
    is_admin, is_center_manager = _user_is_admin_or_center_manager(user)
    if not (is_admin or is_center_manager):
        raise PermissionDenied

    base_enrollments = Enrollment.objects.select_related("klass__center")

    if is_center_manager:
        if user.center_id:
            base_enrollments = base_enrollments.filter(klass__center_id=user.center_id)
            centers = Center.objects.filter(id=user.center_id)
        else:
            base_enrollments = base_enrollments.none()
            centers = Center.objects.none()
    else:
        centers = Center.objects.order_by("name")

    filterset = EnrollmentSummaryFilter(
        data=request.GET or None,
        queryset=base_enrollments,
        request=request,
    )
    center_field = filterset.form.fields.get("center")
    if center_field is not None:
        center_field.queryset = centers

    enrollments = filterset.qs

    stats_qs = enrollments.values("status").annotate(total=Count("pk")).order_by("status")
    status_map = {code: label for code, label in EnrollmentStatus.choices}
    stats = [
        {"status": item["status"], "label": status_map.get(item["status"], item["status"]), "total": item["total"]}
        for item in stats_qs
    ]
    recent = enrollments.order_by("-joined_at")[:5]

    selected_center = user.center if is_center_manager else None
    if not selected_center and filterset.form.is_bound and filterset.form.is_valid():
        selected_center = filterset.form.cleaned_data.get("center")

    context = {
        "stats": stats,
        "recent": recent,
        "center": selected_center,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="EnrollmentSummary",
            target_id="filterable-content",
        )
    )

    if is_htmx_request(request):
        return render(request, "_enrollment_summary_filterable_content.html", context)
    return render(request, "enrollment_summary.html", context)


def _build_filter_ui_context(
    request,
    filterset,
    *,
    model_name,
    target_id="filterable-content",
    data=None,
):
    params_source = data if data is not None else request.GET
    active_filter_badges = build_filter_badges(filterset)

    current_query = _ensure_mutable_querydict(params_source)
    current_query.pop("page", None)
    current_query_params = current_query.urlencode()

    saved_filters = SavedFilter.objects.filter(model_name=model_name).filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    active_filter_name = determine_active_filter_name(
        request, saved_filters, query_params=current_query
    )

    return {
        "filter": filterset,
        "active_filter_badges": active_filter_badges,
        "active_filter_name": active_filter_name,
        "current_query_params": current_query_params,
        "model_name": model_name,
        "target_id": target_id,
    }


def _ensure_mutable_querydict(params_source):
    if isinstance(params_source, QueryDict):
        cloned = params_source.copy()
        cloned._mutable = True
        return cloned

    qd = QueryDict("", mutable=True)
    if not params_source:
        return qd

    items = params_source.items() if hasattr(params_source, "items") else params_source
    for key, value in items:
        if isinstance(value, (list, tuple)):
            for item in value:
                qd.appendlist(key, item)
        else:
            qd.appendlist(key, value)
    return qd


@login_required
def student_report(request):
    context = _build_student_report_context(request, paginate=True)
    if is_htmx_request(request):
        return render(request, "_student_report_filterable_content.html", context)
    return render(request, "student_report.html", context)


@login_required
def student_report_detail(request, pk):
    base_enrollments = _student_report_accessible_enrollments(request.user)
    enrollment = get_object_or_404(base_enrollments, pk=pk)

    start_date = _parse_date_safe(request.GET.get("start_date"))
    end_date = _parse_date_safe(request.GET.get("end_date"))
    row = _student_report_rows([enrollment], start_date=start_date, end_date=end_date)[0]

    back_params = request.GET.urlencode()
    back_url = reverse("reports:student_report")
    if back_params:
        back_url = f"{back_url}?{back_params}"

    return render(
        request,
        "student_report_detail.html",
        {
            "row": row,
            "back_url": back_url,
            "start_date": start_date,
            "end_date": end_date,
            "session_detail_url_name": "reports:student_session_detail",
        },
    )


@login_required
def student_session_detail(request, enrollment_id, session_id):
    base_enrollments = _student_report_accessible_enrollments(request.user)
    enrollment = get_object_or_404(base_enrollments, pk=enrollment_id)
    session = get_object_or_404(ClassSession, pk=session_id, klass_id=enrollment.klass_id)

    attendance = Attendance.objects.filter(student=enrollment.student, session=session).first()
    assessment = Assessment.objects.filter(student=enrollment.student, session=session).first()
    products = StudentProduct.objects.filter(student=enrollment.student, session=session).order_by("-created_at")

    flags = _role_flags(request.user)
    can_upload_session_photo = flags["is_admin"] or flags["is_center_manager"] or flags["is_teacher"]
    if request.method == "POST":
        if not can_upload_session_photo:
            raise PermissionDenied
        form = ClassSessionPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.session = session
            photo.uploaded_by = request.user
            photo.save()
            redirect_url = request.path
            if request.GET:
                redirect_url = f"{redirect_url}?{request.GET.urlencode()}"
            return redirect(redirect_url)
        session_photo_form = form
    else:
        session_photo_form = ClassSessionPhotoForm()

    session_photos = ClassSessionPhoto.objects.filter(session=session).select_related("uploaded_by").order_by("-created_at")

    back_params = request.GET.urlencode()
    back_url = reverse("reports:student_report_detail", args=[enrollment_id])
    if back_params:
        back_url = f"{back_url}?{back_params}"

    return render(
        request,
        "student_session_detail.html",
        {
            "enrollment": enrollment,
            "session": session,
            "attendance": attendance,
            "assessment": assessment,
            "products": products,
            "session_photos": session_photos,
            "session_photo_form": session_photo_form,
            "can_upload_session_photo": can_upload_session_photo,
            "back_url": back_url,
        },
    )


@login_required
def revenue_report(request):
    flags = _role_flags(request.user)
    allowed = flags["is_admin"] or flags["is_center_manager"] or request.user.has_perm("reports.view_revenue_report")
    if not allowed:
        raise PermissionDenied

    base_entries = BillingEntry.objects.select_related(
        "enrollment__klass__center", "enrollment__klass", "enrollment__student"
    )
    if flags["is_center_manager"]:
        if request.user.center_id:
            base_entries = base_entries.filter(enrollment__klass__center_id=request.user.center_id)
        else:
            base_entries = base_entries.none()

    center_ids = base_entries.values_list("enrollment__klass__center_id", flat=True).distinct()
    centers = Center.objects.filter(id__in=center_ids).order_by("name")
    enrollment_ids = base_entries.values_list("enrollment_id", flat=True).distinct()
    enrollment_options = (
        Enrollment.objects.filter(id__in=enrollment_ids)
        .select_related("klass", "student")
        .order_by("student__last_name", "student__first_name", "klass__name")
    )

    filterset = RevenueReportFilter(
        data=request.GET or None,
        queryset=base_entries,
        request=request,
    )
    center_field = filterset.form.fields.get("center")
    if center_field is not None:
        center_field.queryset = centers
    enrollment_field = filterset.form.fields.get("enrollment")
    if enrollment_field is not None:
        enrollment_field.queryset = enrollment_options

    entries = filterset.qs

    totals = entries.aggregate(total_amount=Sum("amount"), total_sessions=Sum("sessions"))
    totals["total_amount"] = totals.get("total_amount") or 0
    totals["total_sessions"] = totals.get("total_sessions") or 0

    by_center = (
        entries.values("enrollment__klass__center__name", "enrollment__klass__center_id")
        .annotate(total_amount=Sum("amount"), total_sessions=Sum("sessions"), entries=Count("id"))
        .order_by("enrollment__klass__center__name")
    )

    ordered_entries = entries.order_by("-created_at", "-id")

    try:
        per_page = int(request.GET.get("per_page", 10))
        if per_page <= 0:
            raise ValueError
    except (TypeError, ValueError):
        per_page = 10

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    paginator = Paginator(ordered_entries, per_page)
    page_obj = paginator.get_page(page_number)

    pagination_query_dict = request.GET.copy()
    if hasattr(pagination_query_dict, "_mutable"):
        pagination_query_dict._mutable = True
    pagination_query_dict.pop("page", None)
    pagination_query_params = pagination_query_dict.urlencode()

    context = {
        "totals": totals,
        "by_center": by_center,
        "recent": page_obj.object_list,
        "paginator": paginator,
        "page_obj": page_obj,
        "per_page": per_page,
        "pagination_query_params": pagination_query_params,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="RevenueReport",
            target_id="filterable-content",
        )
    )

    if is_htmx_request(request):
        return render(request, "_revenue_report_filterable_content.html", context)
    return render(request, "revenue_report.html", context)


@login_required
def teaching_hours_report(request):
    flags = _role_flags(request.user)
    allowed = (
        flags["is_admin"]
        or flags["is_center_manager"]
        or flags["is_teacher"]
        or flags["is_assistant"]
        or request.user.has_perm("reports.view_teaching_hours_report")
        or request.user.is_staff
    )
    if not allowed:
        raise PermissionDenied

    base_sessions = (
        ClassSession.objects.select_related("klass", "klass__center", "klass__main_teacher", "teacher_override")
        .prefetch_related("assistants")
    )

    if flags["is_center_manager"]:
        if request.user.center_id:
            base_sessions = base_sessions.filter(klass__center_id=request.user.center_id)
        else:
            base_sessions = base_sessions.none()

    if flags["is_teacher"] or flags["is_assistant"]:
        base_sessions = base_sessions.filter(
            Q(klass__main_teacher=request.user)
            | Q(teacher_override=request.user)
            | Q(assistants=request.user)
        ).distinct()

    center_ids = base_sessions.values_list("klass__center_id", flat=True).distinct()
    centers = Center.objects.filter(id__in=center_ids).order_by("name")
    teacher_ids = list(base_sessions.values_list("klass__main_teacher_id", flat=True))
    override_ids = list(base_sessions.values_list("teacher_override_id", flat=True))
    assistant_ids = list(base_sessions.values_list("assistants__id", flat=True))
    person_ids = {pk for pk in teacher_ids + override_ids + assistant_ids if pk}
    person_options = User.objects.filter(id__in=person_ids).order_by("last_name", "first_name")

    filterset = TeachingHoursReportFilter(
        data=request.GET or None,
        queryset=base_sessions,
        request=request,
    )
    center_field = filterset.form.fields.get("center")
    if center_field is not None:
        center_field.queryset = centers
    person_field = filterset.form.fields.get("person")
    if person_field is not None:
        person_field.queryset = person_options

    sessions = filterset.qs

    person_stats = {}

    def _touch(user_obj, role_label, status, duration_hours):
        if not user_obj:
            return
        key = user_obj.id
        if key not in person_stats:
            person_stats[key] = {
                "user": user_obj,
                "role_label": role_label,
                "sessions_total": 0,
                "sessions_done": 0,
                "sessions_cancelled": 0,
                "sessions_missed": 0,
                "hours_total": 0.0,
                "hours_done": 0.0,
            }
        data = person_stats[key]
        data["sessions_total"] += 1
        data["hours_total"] += duration_hours
        if status == "DONE":
            data["sessions_done"] += 1
            data["hours_done"] += duration_hours
        elif status == "CANCELLED":
            data["sessions_cancelled"] += 1
        elif status == "MISSED":
            data["sessions_missed"] += 1

    for session in sessions:
        duration_hours = _session_duration_hours(session)
        primary_teacher = session.teacher_override or session.klass.main_teacher
        _touch(primary_teacher, "Giáo viên", session.status, duration_hours)
        for assistant in session.assistants.all():
            _touch(assistant, "Trợ giảng", session.status, duration_hours)

    rows = sorted(person_stats.values(), key=lambda x: (-x["hours_total"], -x["sessions_total"]))

    per_page_default = 10
    try:
        per_page = int(request.GET.get("per_page", per_page_default))
    except (TypeError, ValueError):
        per_page = per_page_default

    page_number = request.GET.get("page") or 1
    paginator = None
    page_obj = None
    display_rows = []

    if rows:
        paginator = Paginator(rows, per_page)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(1)
        display_rows = list(page_obj.object_list)
    else:
        display_rows = []

    context = {
        "rows": display_rows,
        "paginator": paginator,
        "page_obj": page_obj,
        "per_page": per_page,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="TeachingHoursReport",
            target_id="filterable-content",
        )
    )

    if is_htmx_request(request):
        return render(request, "_teaching_hours_report_filterable_content.html", context)
    return render(request, "teaching_hours_report.html", context)


@login_required
def class_activity_report(request):
    flags = _role_flags(request.user)
    if not (flags["is_admin"] or flags["is_center_manager"] or request.user.has_perm("reports.view_class_activity_report")):
        raise PermissionDenied

    base_classes = Class.objects.select_related("center", "main_teacher", "subject")
    if flags["is_center_manager"]:
        if request.user.center_id:
            base_classes = base_classes.filter(center_id=request.user.center_id)
        else:
            base_classes = base_classes.none()

    center_ids = base_classes.values_list("center_id", flat=True).distinct()
    centers = Center.objects.filter(id__in=center_ids).order_by("name")
    teacher_ids = list(base_classes.values_list("main_teacher_id", flat=True))
    teacher_options = User.objects.filter(id__in=teacher_ids).order_by("last_name", "first_name")

    filterset = ClassActivityReportFilter(
        data=request.GET or None,
        queryset=base_classes,
        request=request,
    )
    center_field = filterset.form.fields.get("center")
    if center_field is not None:
        center_field.queryset = centers
    teacher_field = filterset.form.fields.get("main_teacher")
    if teacher_field is not None:
        teacher_field.queryset = teacher_options

    classes = filterset.qs.distinct()

    per_page_default = 10
    try:
        per_page = int(request.GET.get("per_page", per_page_default))
    except (TypeError, ValueError):
        per_page = per_page_default

    page_number = request.GET.get("page") or 1
    paginator = None
    page_obj = None
    classes_page = []

    if classes.exists():
        paginator = Paginator(classes, per_page)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(1)
        classes_page = list(page_obj.object_list)
    else:
        classes_page = []

    start_date = None
    end_date = None
    if filterset.form.is_bound and filterset.form.is_valid():
        start_date = filterset.form.cleaned_data.get("start_date")
        end_date = filterset.form.cleaned_data.get("end_date")

    class_ids = [klass.id for klass in classes_page]
    sessions = (
        ClassSession.objects.filter(klass_id__in=class_ids).select_related("klass")
        if class_ids
        else ClassSession.objects.none()
    )
    if start_date:
        sessions = sessions.filter(date__gte=start_date)
    if end_date:
        sessions = sessions.filter(date__lte=end_date)

    sessions_by_class = {}
    session_ids = []
    for s in sessions:
        sessions_by_class.setdefault(s.klass_id, []).append(s)
        session_ids.append(s.id)

    attendance_counts = {}
    if session_ids:
        for row in (
            Attendance.objects.filter(session_id__in=session_ids)
            .values("session__klass_id", "status")
            .annotate(total=Count("id"))
        ):
            klass_id = row["session__klass_id"]
            status = row["status"]
            attendance_counts.setdefault(klass_id, {"P": 0, "A": 0, "L": 0})
            attendance_counts[klass_id][status] = row["total"]

    submission_counts = {}
    if session_ids:
        for row in (
            StudentExerciseSubmission.objects.filter(session_id__in=session_ids)
            .values("session__klass_id")
            .annotate(total=Count("id"))
        ):
            submission_counts[row["session__klass_id"]] = row["total"]

    product_counts = {}
    if session_ids:
        for row in (
            StudentProduct.objects.filter(session_id__in=session_ids)
            .values("session__klass_id")
            .annotate(total=Count("id"))
        ):
            product_counts[row["session__klass_id"]] = row["total"]

    rows = []
    for klass in classes_page:
        klass_sessions = sessions_by_class.get(klass.id, [])
        total_sessions = len(klass_sessions)
        done_sessions = len([s for s in klass_sessions if s.status == "DONE"])
        cancelled_sessions = len([s for s in klass_sessions if s.status == "CANCELLED"])
        missed_sessions = len([s for s in klass_sessions if s.status == "MISSED"])
        attendance = attendance_counts.get(klass.id, {"P": 0, "A": 0, "L": 0})
        students_count = Enrollment.objects.filter(klass=klass, active=True).count()
        submissions = submission_counts.get(klass.id, 0)
        products = product_counts.get(klass.id, 0)
        rows.append(
            {
                "klass": klass,
                "students_count": students_count,
                "total_sessions": total_sessions,
                "done_sessions": done_sessions,
                "cancelled_sessions": cancelled_sessions,
                "missed_sessions": missed_sessions,
                "attendance": attendance,
                "submissions": submissions,
                "products": products,
                "products_per_session": round(products / total_sessions, 2) if total_sessions else 0,
            }
        )

    context = {
        "rows": rows,
        "paginator": paginator,
        "page_obj": page_obj,
        "per_page": per_page,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="ClassActivityReport",
            target_id="filterable-content",
        )
    )

    if is_htmx_request(request):
        return render(request, "_class_activity_report_filterable_content.html", context)
    return render(request, "class_activity_report.html", context)


@login_required
def student_report_pdf(request):
    try:
        from weasyprint import HTML
    except ImportError:
        return HttpResponse(
            "Thiếu thư viện weasyprint. Vui lòng cài đặt weasyprint để xuất PDF.",
            status=500,
        )

    context = _build_student_report_context(request, paginate=False)
    html_string = render_to_string("student_report_pdf.html", context | {"is_pdf": True})
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="bao-cao-hoc-sinh.pdf"'
    return response
