from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from apps.common.utils.http import is_htmx_request
from apps.reports.views import _build_student_report_context
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
	context.update(
		{
			"page_title": "Báo cáo học tập của con",
			"page_description": "Tổng hợp điểm danh, tiến độ, đánh giá và sản phẩm của các con theo từng lớp.",
		}
	)
	if is_htmx_request(request):
		return render(request, "_student_report_filterable_content.html", context)
	return render(request, "children_report.html", context)
