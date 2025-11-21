from django.contrib import admin

from apps.billing.models import BillingEntry, Discount


@admin.register(BillingEntry)
class BillingEntryAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "entry_type",
        "sessions",
        "unit_price",
        "discount",
        "discount_amount",
        "amount",
        "created_at",
        "note",
    )
    list_filter = ("entry_type", "discount")
    search_fields = (
        "enrollment__student__username",
        "enrollment__klass__code",
        "note",
    )
    autocomplete_fields = ("enrollment",)
    ordering = ("-created_at",)


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "percent", "amount", "max_amount", "active", "usage_count")
    list_filter = ("active",)
    search_fields = ("code", "name")
