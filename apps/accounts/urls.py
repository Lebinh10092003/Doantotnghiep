from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "accounts"
urlpatterns = [
    #Đăng nhập và đăng xuất
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    # Quản lý hồ sơ cá nhân
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
    path("profile/change-password/", views.change_password_view, name="change_password"),
    #Quản lý người dùng
    path("manage/", views.manage_accounts, name="manage_accounts"),
    path("add/", views.user_create_view, name="add_user"),
    path("delete/", views.user_delete_view, name="delete_users"),
    path("edit/<int:user_id>/", views.user_edit_view, name="edit_user"),
    path("<int:user_id>/detail/", views.user_detail_view, name="user_detail"),
    path("export/", views.export_users_view, name="export_users"),
    path("import/", views.import_users_view, name="import_users"),
    path("import/template/", views.export_import_template_view, name="import_template"),
    #Quản lý nhóm người dùng
    path("groups/", views.manage_groups, name="manage_groups"),
    path("groups/view/<int:group_id>/", views.group_view, name="group_view"),
    path("groups/<int:group_id>/users/", views.group_users_view, name="group_users"),
    path("groups/create/", views.group_create_view, name="group_create"),
    path("groups/edit/<int:group_id>/", views.group_edit_view, name="group_edit"),
    path("groups/delete/", views.group_delete_view, name="group_delete"),
    
]
