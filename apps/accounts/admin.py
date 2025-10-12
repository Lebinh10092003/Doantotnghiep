# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import ParentStudentRelation

User = get_user_model()

class ParentStudentInline(admin.TabularInline):
    model = ParentStudentRelation
    fk_name = "parent"
    extra = 0
    verbose_name = "Child"
    verbose_name_plural = "Children"
    raw_id_fields = ("student",)
    fields = ("student", "note")

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "username", "email", "role", "center", "is_active", "is_staff")
    list_filter = ("role", "center", "is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    ordering = ("username",)
    inlines = [ParentStudentInline]

    # mở rộng fieldsets để chứa các field tùy chỉnh của User
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            _("Profile"),
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

    # tối ưu hiển thị tên đầy đủ
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    get_full_name.short_description = "Full name"

@admin.register(ParentStudentRelation)
class ParentStudentRelationAdmin(admin.ModelAdmin):
    list_display = ("id", "parent", "student", "note")
    search_fields = (
        "parent__username",
        "parent__email",
        "student__username",
        "student__email",
    )
    list_filter = ("parent",)
    raw_id_fields = ("parent", "student")
