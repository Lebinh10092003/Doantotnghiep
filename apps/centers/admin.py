from django.contrib import admin
from .models import Center, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "address", "phone", "email")
    search_fields = ("name", "code", "address", "phone", "email")
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "center", "note")
    list_filter = ("center",)
    search_fields = ("name", "center__name", "center__code")
    ordering = ("center__name", "name")