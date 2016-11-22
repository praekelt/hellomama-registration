from django.contrib import admin

from .models import Record


class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "write_to", "created_at", "updated_at"]
    list_filter = ["write_to", "created_at"]
    search_fields = ["identity", "write_to"]
    actions = ["regenerate_personnel_code"]

    def regenerate_personnel_code(self, request, queryset):
        created = 0
        skipped = 0
        for record in queryset:
            if record.write_to != "personnel_code":
                skipped += 1
                continue
            Record.objects.create(
                identity=record.identity, write_to="personnel_code",
                length=record.length, created_by=request.user)
            created += 1
        if created == 1:
            created_text = "%s Record was" % created
        else:
            created_text = "%s Records were" % created
        if skipped == 1:
            skipped_text = "%s Record was" % skipped
        else:
            skipped_text = "%s Records were" % skipped
        self.message_user(
            request, "%s successfully changed. %s skipped because they are "
            "not a HCW." % (created_text, skipped_text))

    regenerate_personnel_code.short_description = "Change code and "\
        "SMS (personnel code only)"

admin.site.register(Record, RecordAdmin)
