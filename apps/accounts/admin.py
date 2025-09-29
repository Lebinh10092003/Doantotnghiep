from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, Permission
from .models import User, ParentStudentRelation


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "center", "is_active", "is_staff")
    list_filter = ("role", "center", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "phone")
    ordering = ("username",)
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "role",
                    "center",
                    "phone",
                    "avatar",
                    "dob",
                    "gender",
                    "national_id",
                    "address",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {"fields": ("role", "center")}),
    )


@admin.register(ParentStudentRelation)
class ParentStudentRelationAdmin(admin.ModelAdmin):
    list_display = ("parent", "student", "note")
    search_fields = (
        "parent__username",
        "parent__email",
        "student__username",
        "student__email",
    )

