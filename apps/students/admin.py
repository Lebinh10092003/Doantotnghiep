from django.contrib import admin
from .models import StudentProduct


@admin.register(StudentProduct)
class StudentProductAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "session", "created_at")
    list_filter = ("session__klass__center",)
    search_fields = (
        "title",
        "student__username",
        "session__klass__code",
        "session__klass__name",
    )
    autocomplete_fields = ("student", "session")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    raw_id_fields = ("student", "session")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("student", "session")
