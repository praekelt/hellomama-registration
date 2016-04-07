from django.contrib import admin


class ChangeAdmin(admin.ModelAdmin):
    list_display = [
        "id", "action", "mother_id", "validated", "source",
        "created_at", "updated_at", "created_by", "updated_by"]
    list_filter = ["source", "validated", "created_at"]
    search_fields = ["mother_id", "to_addr"]

from .models import Change

admin.site.register(Change, ChangeAdmin)
