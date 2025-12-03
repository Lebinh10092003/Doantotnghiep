from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
	path("children/", views.children_overview, name="children_overview"),
	path(
		"children/photos/",
		views.children_overview,
		{"default_tab": "photos"},
		name="children_overview_photos",
	),
	path("children/report/", views.children_report, name="children_report"),
	path("children/report/<int:pk>/", views.children_report_detail, name="children_report_detail"),
	path(
		"children/report/<int:enrollment_id>/sessions/<int:session_id>/",
		views.children_session_detail,
		name="children_session_detail",
	),
]
