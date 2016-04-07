from django.contrib import admin
from .models import Source, Registration


class RegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "id", "stage", "validated", "mother_id", "source",
        "created_at", "updated_at", "created_by", "updated_by"]
    list_filter = ["source", "validated", "created_at"]
    search_fields = ["mother_id", "to_addr"]

admin.site.register(Source)
admin.site.register(Registration, RegistrationAdmin)
