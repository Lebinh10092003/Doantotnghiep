from django.contrib import admin
from .models import Subject, Module, Lesson, Lecture, Exercise


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ("order", "title")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "order")
    list_filter = ("subject",)
    search_fields = ("title", "subject__name", "subject__code")
    inlines = [LessonInline]


class LectureInline(admin.StackedInline):
    model = Lecture
    extra = 0


class ExerciseInline(admin.StackedInline):
    model = Exercise
    extra = 0


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "order")
    list_filter = ("module__subject", "module")
    search_fields = ("title", "module__title", "module__subject__name")
    inlines = [LectureInline, ExerciseInline]
