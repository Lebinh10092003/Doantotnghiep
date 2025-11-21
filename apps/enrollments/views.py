import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ParentStudentRelation, User
from apps.classes.models import Class
from apps.centers.models import Center
from apps.enrollments.forms import EnrollmentForm
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.enrollments.filters import EnrollmentFilter
from django.http import QueryDict, HttpResponse
from apps.filters.models import SavedFilter
from django import forms


def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


def _role_flags(user):
    role = (getattr(user, "role", "") or "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()

    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group(
        "CENTER_MANAGER"
    )
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_assistant = role == "ASSISTANT" or in_group("Assistant") or in_group("ASSISTANT")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")
    is_student = role == "STUDENT" or in_group("Student") or in_group("STUDENT")

    return {
        "is_admin": is_admin,
        "is_center_manager": is_center_manager,
        "is_teacher": is_teacher,
        "is_assistant": is_assistant,
        "is_parent": is_parent,
        "is_student": is_student,
        "can_manage": is_admin or is_center_manager,
    }


def _get_managed_classes(user, flags):
    if flags["is_admin"]:
        return Class.objects.select_related("center", "subject").order_by("code")
    if flags["is_center_manager"] and user.center:
        return (
            Class.objects.filter(center=user.center)
            .select_related("center", "subject")
            .order_by("code")
        )
    return Class.objects.none()


@login_required
def enrollment_list(request):
    user = request.user
    flags = _role_flags(user)
    if not any(
        [
            flags["is_admin"],
            flags["is_center_manager"],
            flags["is_teacher"],
            flags["is_assistant"],
            flags["is_parent"],
            flags["is_student"],
        ]
    ):
        raise PermissionDenied

    enrollments = Enrollment.objects.select_related(
        "student", "klass", "klass__center", "klass__subject"
    )

    if flags["is_center_manager"]:
        if not user.center:
            raise PermissionDenied
        enrollments = enrollments.filter(klass__center=user.center)
        if not center_id:
            center_id = str(user.center_id)
    elif flags["is_teacher"] or flags["is_assistant"]:
        teaching_classes = (
            Class.objects.filter(Q(main_teacher=user) | Q(assistants=user))
            .select_related("center", "subject")
            .distinct()
        )
        enrollments = enrollments.filter(klass_id__in=teaching_classes.values_list("id", flat=True))
    elif flags["is_parent"]:
        children_ids = list(
            ParentStudentRelation.objects.filter(parent=user).values_list("student_id", flat=True)
        )
        enrollments = enrollments.filter(student_id__in=children_ids)
    elif flags["is_student"]:
        enrollments = enrollments.filter(student=user)

    enrollment_filter = EnrollmentFilter(request.GET, queryset=enrollments)
    enrollments = enrollment_filter.qs

    center_id = request.GET.get("center")
    klass_id = request.GET.get("klass")
    status = request.GET.get("status")
    student_query = request.GET.get("student", "").strip()
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    allowed_orders = {"joined_at", "-joined_at", "start_date", "-start_date"}
    order = request.GET.get("order", "-joined_at")
    if order not in allowed_orders:
        order = "-joined_at"
    enrollments = enrollments.order_by(order)

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

    paginator = Paginator(enrollments, per_page)
    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(1)
    paginated_enrollments = page_obj.object_list

    if flags["is_admin"]:
        centers = Center.objects.order_by("name")
    elif flags["is_center_manager"] and user.center:
        centers = Center.objects.filter(id=user.center_id)
    else:
        centers = Center.objects.filter(
            classes__enrollments__in=enrollments
        ).distinct()

    klass_choices = _get_managed_classes(user, flags)
    if not flags["can_manage"]:
        klass_choices = (
            Class.objects.filter(id__in=enrollments.values_list("klass_id", flat=True))
            .select_related("center", "subject")
            .distinct()
        )

    active_filter_badges = []
    if enrollment_filter.form.is_bound:
        for name, value in enrollment_filter.form.cleaned_data.items():
            if value and name in enrollment_filter.form.fields:
                field_label = enrollment_filter.form.fields[name].label or name
                display_value = ""
                field = enrollment_filter.form.fields[name]

                if isinstance(value, (Center, Class, User)):
                    display_value = str(value)
                elif isinstance(field, forms.ChoiceField):
                    display_value = dict(field.choices).get(value) if value else None
                elif isinstance(value, slice):
                    start_v, end_v = value.start, value.stop
                    if start_v and end_v:
                        display_value = f"từ {start_v.strftime('%d/%m/%Y')} đến {end_v.strftime('%d/%m/%Y')}"
                    elif start_v:
                        display_value = f"từ {start_v.strftime('%d/%m/%Y')}"
                    elif end_v:
                        display_value = f"đến {end_v.strftime('%d/%m/%Y')}"
                elif isinstance(value, str):
                    display_value = value

                if display_value:
                    active_filter_badges.append(
                        {"label": field_label, "value": display_value, "key": name}
                    )

    quick_filters = [
        {"name": "Đang học", "params": "status=ACTIVE"},
        {"name": "Bảo lưu", "params": "status=PAUSED"},
        {"name": "Nghỉ học", "params": "status=CANCELLED"},
        {"name": "Mới", "params": "status=NEW"},
    ]

    saved_filters = SavedFilter.objects.filter(model_name="Enrollment").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()

    active_filter_name = None
    current_params_dict = {
        k: v_list for k, v_list in request.GET.lists() if k not in ["page", "per_page"]
    }
    if current_params_dict:
        for qf in quick_filters:
            qf_dict = {k: v_list for k, v_list in QueryDict(qf["params"]).lists()}
            if qf_dict == current_params_dict:
                active_filter_name = qf["name"]
                break
        if not active_filter_name:
            for sf in saved_filters:
                try:
                    sf_dict = sf.query_params
                    if sf_dict == current_params_dict:
                        active_filter_name = sf.name
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

    query_params_no_page = request.GET.copy()
    query_params_no_page._mutable = True
    for key in ["page", "per_page"]:
        query_params_no_page.pop(key, None)
    current_query_params = query_params_no_page.urlencode()

    context = {
        "enrollments": paginated_enrollments,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "current_query_params": current_query_params,
        "filter": enrollment_filter,
        "quick_filters": quick_filters,
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
        "model_name": "Enrollment",
        "flags": flags,
        "status_choices": EnrollmentStatus.choices,
        "centers": centers,
        "classes": klass_choices,
        "filter_params": {
            "center": center_id or "",
            "klass": klass_id or "",
            "status": status or "",
            "student": student_query,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "order": order,
        },
    }
    if is_htmx_request(request):
        return render(request, "_enrollment_filterable_content.html", context)
    return render(request, "enrollment_list.html", context)


def _require_manage_permission(user, flags):
    if not flags["can_manage"]:
        raise PermissionDenied


def _ensure_scope(enrollment, user, flags):
    if flags["is_admin"]:
        return
    if flags["is_center_manager"]:
        if not user.center or enrollment.klass.center_id != user.center_id:
            raise PermissionDenied
    else:
        raise PermissionDenied


@login_required
def enrollment_create(request):
    user = request.user
    flags = _role_flags(user)
    _require_manage_permission(user, flags)
    klass_queryset = _get_managed_classes(user, flags)

    if request.method == "POST":
        form = EnrollmentForm(
            request.POST, klass_queryset=klass_queryset
        )
        if form.is_valid():
            enrollment = form.save()
            if is_htmx_request(request):
                response = HttpResponse(status=204)
                response["HX-Trigger"] = json.dumps(
                    {
                        "reload-enrollments-table": True,
                        "closeEnrollmentModal": True,
                        "show-sweet-alert": {
                            "icon": "success",
                            "title": f"Đã tạo ghi danh cho {enrollment.student}",
                        },
                    }
                )
                return response
            messages.success(request, "Đã tạo ghi danh mới.")
            return redirect("enrollments:list")
    else:
        form = EnrollmentForm(klass_queryset=klass_queryset)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(request, "_enrollment_form.html", context)


@login_required
def enrollment_update(request, pk):
    user = request.user
    flags = _role_flags(user)
    _require_manage_permission(user, flags)
    enrollment = get_object_or_404(Enrollment, pk=pk)
    _ensure_scope(enrollment, user, flags)
    klass_queryset = _get_managed_classes(user, flags)

    if request.method == "POST":
        form = EnrollmentForm(
            request.POST, instance=enrollment, klass_queryset=klass_queryset
        )
        if form.is_valid():
            enrollment = form.save()
            if is_htmx_request(request):
                response = HttpResponse(status=204)
                response["HX-Trigger"] = json.dumps(
                    {
                        "reload-enrollments-table": True,
                        "closeEnrollmentModal": True,
                        "show-sweet-alert": {
                            "icon": "success",
                            "title": "Đã cập nhật ghi danh.",
                        },
                    }
                )
                return response
            messages.success(request, "Đã cập nhật ghi danh.")
            return redirect("enrollments:list")
    else:
        form = EnrollmentForm(instance=enrollment, klass_queryset=klass_queryset)

    context = {
        "form": form,
        "is_create": False,
        "enrollment": enrollment,
    }
    return render(request, "_enrollment_form.html", context)


@login_required
@require_POST
def enrollment_cancel(request, pk):
    user = request.user
    flags = _role_flags(user)
    _require_manage_permission(user, flags)
    enrollment = get_object_or_404(Enrollment, pk=pk)
    _ensure_scope(enrollment, user, flags)

    enrollment.status = EnrollmentStatus.CANCELLED
    enrollment.save()
    messages.success(request, "Đã hủy ghi danh.")
    return redirect("enrollments:list")
