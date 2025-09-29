from django.contrib import admin
from .models import Class, ClassAssistant, ClassSession


class ClassSessionInline(admin.TabularInline):
    model = ClassSession
    extra = 0
    fields = ("index", "date", "lesson", "status", "teacher_override", "room_override")


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "center",
        "subject",
        "status",
        "main_teacher",
        "start_date",
        "end_date",
    )
    list_filter = ("center", "subject", "status")
    search_fields = ("code", "name", "main_teacher__username")
    inlines = [ClassSessionInline]
    autocomplete_fields = ("main_teacher",)


@admin.register(ClassAssistant)
class ClassAssistantAdmin(admin.ModelAdmin):
    list_display = ("klass", "assistant", "scope")
    list_filter = ("scope", "klass__center")
    search_fields = ("klass__code", "klass__name", "assistant__username")
    autocomplete_fields = ("assistant", "klass")


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = (
        "klass",
        "index",
        "date",
        "lesson",
        "status",
        "teacher_override",
        "room_override",
    )
    list_filter = ("status", "klass__center", "klass__subject")
    search_fields = ("klass__code", "klass__name", "lesson__title")
    autocomplete_fields = ("lesson", "teacher_override", "assistants", "room_override")
    filter_horizontal = ("assistants",)
