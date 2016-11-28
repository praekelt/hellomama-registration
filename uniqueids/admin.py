from django.contrib import admin

from .models import Record
from .tasks import send_personnel_code


class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "write_to", "created_at", "updated_at"]
    list_filter = ["write_to", "created_at"]
    search_fields = ["identity", "write_to"]
    actions = ["resend_personnel_code"]

    def resend_personnel_code(self, request, queryset):
        created = 0
        for record in queryset.filter(write_to="personnel_code").iterator():
            send_personnel_code.apply_async(kwargs={
                "identity": str(record.identity),
                "personnel_code": record.id})
            created += 1
        if created == 1:
            created_text = "%s Record was" % created
        else:
            created_text = "%s Records were" % created
        self.message_user(request, "%s resent." % created_text)

    resend_personnel_code.short_description = "Send code by SMS (personnel "\
        "code only)"

admin.site.register(Record, RecordAdmin)
