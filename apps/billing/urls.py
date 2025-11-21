from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("", views.billing_home, name="home"),
    path("enrollments/<int:enrollment_id>/", views.billing_entries, name="entries"),
    path("enrollments/<int:enrollment_id>/purchase/", views.billing_purchase, name="purchase"),
    path("discounts/", views.discount_list, name="discount_list"),
    path("discounts/new/", views.discount_create, name="discount_create"),
    path("discounts/<int:pk>/edit/", views.discount_update, name="discount_update"),
    path("discounts/<int:pk>/delete/", views.discount_delete, name="discount_delete"),
]
