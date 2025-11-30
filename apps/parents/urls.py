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
]
