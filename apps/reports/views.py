from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render

from apps.centers.models import Center
from apps.enrollments.models import Enrollment, EnrollmentStatus


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
