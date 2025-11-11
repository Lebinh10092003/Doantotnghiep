from django.contrib import admin
from .models import Class, ClassAssistant, ClassSchedule

class ClassScheduleInline(admin.TabularInline):
    model = ClassSchedule
    extra = 1
    verbose_name = "Lịch học hàng tuần"

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
    inlines = [ClassScheduleInline]
    autocomplete_fields = ("main_teacher",)


@admin.register(ClassAssistant)
class ClassAssistantAdmin(admin.ModelAdmin):
    list_display = ("klass", "assistant", "scope")
    list_filter = ("scope", "klass__center")
    search_fields = ("klass__code", "klass__name", "assistant__username")
    autocomplete_fields = ("assistant", "klass")