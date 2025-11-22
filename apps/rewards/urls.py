from django.urls import path
from . import views

app_name = "rewards"

urlpatterns = [
    path("account/", views.account_summary, name="account_summary"),
    path("catalog/", views.catalog, name="catalog"),
    path("requests/", views.my_requests, name="my_requests"),
    path("requests/submit/", views.submit_request, name="submit_request"),
    path("award/", views.award_points, name="award_points"),
    path("manage/items/", views.manage_items, name="manage_items"),
    path("manage/requests/", views.manage_requests, name="manage_requests"),
    path("manage/requests/<int:pk>/approve/", views.approve_request, name="approve_request"),
    path("manage/requests/<int:pk>/reject/", views.reject_request, name="reject_request"),
    path("manage/requests/<int:pk>/fulfill/", views.fulfill_request, name="fulfill_request"),
    path("manage/requests/<int:pk>/cancel/", views.cancel_request, name="cancel_request"),
]
