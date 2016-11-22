from django.contrib import admin

# Register your models here.
from .models import Record


class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "write_to", "created_at", "updated_at"]
    list_filter = ["write_to", "created_at"]
    search_fields = ["identity", "write_to"]


admin.site.register(Record, RecordAdmin)
