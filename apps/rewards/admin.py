from django.contrib import admin
from .models import PointAccount, RewardItem, RewardTransaction, RedemptionRequest, RedemptionStatus


@admin.register(PointAccount)
class PointAccountAdmin(admin.ModelAdmin):
    list_display = ("student", "balance")
    search_fields = ("student__username", "student__email")
    autocomplete_fields = ("student",)
    ordering = ("-balance",)


@admin.register(RewardItem)
class RewardItemAdmin(admin.ModelAdmin):
    list_display = ("name", "cost", "stock", "is_active")
    search_fields = ("name",)
    ordering = ("-is_active", "-stock")
    list_filter = ("is_active",)


@admin.register(RewardTransaction)
class RewardTransactionAdmin(admin.ModelAdmin):
    list_display = ("student", "delta", "item", "reason", "created_at")
    list_filter = ("item",)
    search_fields = ("student__username", "reason")
    autocomplete_fields = ("student", "item")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(RedemptionRequest)
class RedemptionRequestAdmin(admin.ModelAdmin):
    list_display = ("student", "item", "quantity", "status", "created_at")
    search_fields = ("student__username", "item__name")
    list_filter = ("status",)
    autocomplete_fields = ("student", "item")
    ordering = ("-created_at",)
