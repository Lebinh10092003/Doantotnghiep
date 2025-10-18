from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("manage/", views.manage_accounts, name="manage_accounts"),
    path("add/", views.user_create_view, name="add_user"),
    path("delete/", views.user_delete_view, name="delete_users"),
    path("edit/<int:user_id>/", views.user_edit_view, name="edit_user"),
    path("<int:user_id>/detail/", views.user_detail_view, name="user_detail"),
    path("export/", views.export_users_view, name="export_users"),
    path("import/", views.import_users_view, name="import_users"),
    path("import/template/", views.export_import_template_view, name="import_template"),
]
