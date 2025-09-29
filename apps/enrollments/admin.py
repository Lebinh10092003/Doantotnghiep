from django.contrib import admin
from .models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("klass", "student", "active", "joined_at")
    list_filter = ("active", "klass__center", "klass__subject")
    search_fields = (
        "klass__code",
        "klass__name",
        "student__username",
        "student__email",
    )
    autocomplete_fields = ("klass", "student")
    ordering = ("-joined_at",)
