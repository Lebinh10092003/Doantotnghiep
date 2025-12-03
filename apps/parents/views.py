from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.common.utils.http import is_htmx_request
from apps.reports.views import (
	_build_student_report_context,
	_student_report_accessible_enrollments,
	_student_report_rows,
	_parse_date_safe,
	_role_flags,
)
from apps.class_sessions.models import ClassSession, ClassSessionPhoto
from apps.class_sessions.forms import ClassSessionPhotoForm
from apps.attendance.models import Attendance
from apps.assessments.models import Assessment
from apps.students.models import StudentProduct
from .services import build_parent_children_snapshot


def _user_is_parent(user):
	role = (getattr(user, "role", "") or "").strip().upper()
	if role == "PARENT":
		return True
	return user.groups.filter(name__iexact="parent").exists()


@login_required
def children_overview(request, default_tab="overview"):
	parent = request.user
	snapshot = build_parent_children_snapshot(parent)
	active_tab = request.GET.get("tab") or default_tab
	context = {
		"children_data": snapshot["children_data"],
		"has_children": snapshot["has_children"],
		"active_tab": active_tab,
		"summary_metrics": snapshot["summary_metrics"],
		"recent_updates": snapshot["recent_updates"],
		"child_display_names": snapshot.get("child_display_names", []),
	}
	return render(request, "children_overview.html", context)


@login_required
def children_report(request):
	if not _user_is_parent(request.user):
		raise PermissionDenied
	context = _build_student_report_context(request, paginate=True)
	context["detail_url_name"] = "parents:children_report_detail"
	context.update(
		{
			"page_title": "Báo cáo học tập của con",
			"page_description": "Tổng hợp điểm danh, tiến độ, đánh giá và sản phẩm của các con theo từng lớp.",
		}
	)
	if is_htmx_request(request):
		return render(request, "_student_report_filterable_content.html", context)
	return render(request, "children_report.html", context)


@login_required
def children_report_detail(request, pk: int):
	if not _user_is_parent(request.user):
		raise PermissionDenied
	base_enrollments = _student_report_accessible_enrollments(request.user)
	enrollment = get_object_or_404(base_enrollments, pk=pk)

	start_date = _parse_date_safe(request.GET.get("start_date"))
	end_date = _parse_date_safe(request.GET.get("end_date"))
	row = _student_report_rows([enrollment], start_date=start_date, end_date=end_date)[0]

	back_params = request.GET.urlencode()
	back_url = reverse("parents:children_report")
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
			"session_detail_url_name": "parents:children_session_detail",
		},
	)


@login_required
def children_session_detail(request, enrollment_id: int, session_id: int):
	if not _user_is_parent(request.user):
		raise PermissionDenied
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
	back_url = reverse("parents:children_report_detail", args=[enrollment_id])
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
