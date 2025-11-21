from django.contrib import admin
from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("klass", "student", "status", "active", "joined_at", "start_date", "end_date")
    list_filter = ("status", "active", "klass__center", "klass__subject")
    search_fields = (
        "klass__code",
        "klass__name",
        "student__username",
        "student__email",
        "student__user_code",
        "student__phone",
    )
    autocomplete_fields = ("klass", "student")
    ordering = ("-joined_at",)
