from django.contrib import admin
from .models import PointAccount, RewardItem, RewardTransaction


@admin.register(PointAccount)
class PointAccountAdmin(admin.ModelAdmin):
    list_display = ("student", "balance")
    search_fields = ("student__username", "student__email")
    autocomplete_fields = ("student",)
    ordering = ("-balance",)


@admin.register(RewardItem)
class RewardItemAdmin(admin.ModelAdmin):
    list_display = ("name", "cost")
    search_fields = ("name",)
    ordering = ("-cost",)


@admin.register(RewardTransaction)
class RewardTransactionAdmin(admin.ModelAdmin):
    list_display = ("student", "delta", "item", "reason", "created_at")
    list_filter = ("item",)
    search_fields = ("student__username", "reason")
    autocomplete_fields = ("student", "item")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
