from datetime import date
from math import ceil
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.accounts.models import ParentStudentRelation
from apps.assessments.models import Assessment
from apps.attendance.models import Attendance
from apps.class_sessions.models import ClassSession, ClassSessionPhoto
from apps.class_sessions.forms import ClassSessionPhotoForm
from apps.classes.models import Class
from apps.centers.models import Center
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.students.models import StudentProduct
from apps.reports.filters import StudentReportFilter
from apps.accounts.models import User


def _user_is_admin_or_center_manager(user):
    role = (getattr(user, "role", "") or "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()
    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = (
        role == "CENTER_MANAGER"
        or in_group("Center Manager")
        or in_group("CENTER_MANAGER")
    )
    return is_admin, is_center_manager


def _role_flags(user):
    role = (getattr(user, "role", "") or "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()
    is_admin = user.is_superuser or user.is_staff or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group("CENTER_MANAGER")
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")
    is_student = role == "STUDENT" or in_group("Student") or in_group("STUDENT")
    return {
        "is_admin": is_admin,
        "is_center_manager": is_center_manager,
        "is_teacher": is_teacher,
        "is_parent": is_parent,
        "is_student": is_student,
    }


def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def enrollment_summary(request):
    user = request.user
    is_admin, is_center_manager = _user_is_admin_or_center_manager(user)
    if not (is_admin or is_center_manager):
        raise PermissionDenied

    enrollments = Enrollment.objects.select_related("klass__center")
    center_id = request.GET.get("center")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if is_center_manager:
        if not user.center:
            raise PermissionDenied
        enrollments = enrollments.filter(klass__center=user.center)
        centers = Center.objects.filter(id=user.center_id)
        center_id = str(user.center_id)
    else:
        centers = Center.objects.order_by("name")
        if center_id:
            enrollments = enrollments.filter(klass__center_id=center_id)

    if start_date:
        enrollments = enrollments.filter(joined_at__gte=start_date)
    if end_date:
        enrollments = enrollments.filter(joined_at__lte=end_date)

    stats_qs = enrollments.values("status").annotate(total=Count("pk")).order_by("status")
    status_map = {code: label for code, label in EnrollmentStatus.choices}
    stats = [
        {"status": item["status"], "label": status_map.get(item["status"], item["status"]), "total": item["total"]}
        for item in stats_qs
    ]
    recent = enrollments.order_by("-joined_at")[:5]

    center_name = centers.filter(id=center_id).values_list("name", flat=True).first() if center_id else None
    filter_badges = []
    if center_id and center_name:
        filter_badges.append({"key": "center", "label": "Trung tâm", "value": center_name})
    if start_date:
        filter_badges.append({"key": "start_date", "label": "Từ ngày", "value": start_date})
    if end_date:
        filter_badges.append({"key": "end_date", "label": "Đến ngày", "value": end_date})

    context = {
        "stats": stats,
        "recent": recent,
        "center": user.center if is_center_manager else centers.filter(id=center_id).first(),
        "centers": centers,
        "filter_params": {"center": center_id or "", "start_date": start_date or "", "end_date": end_date or ""},
        "filter_badges": filter_badges,
    }
    return render(request, "enrollment_summary.html", context)


def _parse_date_safe(value: str | None) -> date | None:
    if not value:
        return None
    return parse_date(value)


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


def _build_student_report_context(request, paginate=True):
    flags = _role_flags(request.user)
    if not (flags["is_admin"] or flags["is_center_manager"] or flags["is_teacher"] or flags["is_parent"] or flags["is_student"]):
        raise PermissionDenied

    base_enrollments = _student_report_accessible_enrollments(request.user)
    centers = (
        Center.objects.filter(id__in=base_enrollments.values_list("klass__center_id", flat=True).distinct())
        .order_by("name")
    )
    classes = (
        Class.objects.filter(id__in=base_enrollments.values_list("klass_id", flat=True).distinct())
        .order_by("code")
    )
    students_qs = User.objects.filter(id__in=base_enrollments.values_list("student_id", flat=True).distinct()).order_by(
        "last_name", "first_name"
    )

    filterset = StudentReportFilter(request.GET, queryset=base_enrollments)
    if "center" in filterset.form.fields:
        filterset.form.fields["center"].queryset = centers
    if "klass" in filterset.form.fields:
        filterset.form.fields["klass"].queryset = classes
    if "student" in filterset.form.fields:
        filterset.form.fields["student"].queryset = students_qs

    enrollments = filterset.qs.distinct().order_by("klass__code", "student__last_name", "student__first_name")

    start_date = _parse_date_safe(request.GET.get("start_date"))
    end_date = _parse_date_safe(request.GET.get("end_date"))

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

    rows = _student_report_rows(enrollments_page, start_date=start_date, end_date=end_date)

    students = (
        base_enrollments.values("student_id", "student__first_name", "student__last_name", "student__username")
        .distinct()
        .order_by("student__last_name")
    )

    filter_badges = []
    if filterset.form.is_bound:
        for name, value in filterset.form.cleaned_data.items():
            if value and name in filterset.form.fields:
                label = filterset.form.fields[name].label or name
                if hasattr(value, "get_full_name"):
                    display = value.get_full_name() or str(value)
                else:
                    display = getattr(value, "name", None) or str(value)
                filter_badges.append({"key": name, "label": label, "value": display})
    if start_date and not any(b["key"] == "start_date" for b in filter_badges):
        filter_badges.append({"key": "start_date", "label": "Từ ngày", "value": start_date.strftime("%d/%m/%Y")})
    if end_date and not any(b["key"] == "end_date" for b in filter_badges):
        filter_badges.append({"key": "end_date", "label": "Đến ngày", "value": end_date.strftime("%d/%m/%Y")})

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
        "filter": filterset,
        "quick_filters": [],
        "active_filter_name": None,
        "active_filter_badges": filter_badges,
        "model_name": "StudentReport",
        "current_query_params": current_query_params,
        "paginator": paginator,
        "page_obj": page_obj,
        "per_page": per_page,
    }
    return context


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
