from django.contrib import admin
from .models import SavedFilter

@admin.register(SavedFilter)
class SavedFilterAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "model_name", "is_public", "created_at")
    list_filter = ("model_name", "is_public", "user")
    search_fields = ("name", "user__username", "query_params")
    raw_id_fields = ("user",)