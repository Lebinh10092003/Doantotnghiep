from django.contrib import admin
from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("session", "student", "status", "note")
    list_filter = ("status", "session__klass__center")
    search_fields = (
        "student__username",
        "session__klass__code",
        "session__klass__name",
    )
    autocomplete_fields = ("session", "student")
    ordering = ("-session__date",)
    raw_id_fields = ("session", "student")
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("session", "student")
