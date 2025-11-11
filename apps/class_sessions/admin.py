from django.contrib import admin
from .models import ClassSession

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = (
        "klass",
        "index",
        "date",
        "start_time", 
        "end_time",  
        "lesson",
        "status",
        "teacher_override",
        "room_override",
    )
    list_filter = ("status", "klass__center", "klass__subject", "date") 
    search_fields = ("klass__code", "klass__name", "lesson__title")
    autocomplete_fields = ("lesson", "teacher_override", "assistants", "room_override", "klass")
    filter_horizontal = ("assistants",)
    ordering = ("-date", "start_time") 