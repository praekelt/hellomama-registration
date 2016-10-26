from django.contrib import admin
from django.conf.urls import url
from django.template.response import TemplateResponse
from .models import Source, Registration, SubscriptionRequest


class RegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "id", "stage", "validated", "mother_id", "source",
        "created_at", "updated_at", "created_by", "updated_by"]
    list_filter = ["source", "validated", "created_at"]
    search_fields = ["mother_id", "to_addr"]

    def get_urls(self):
        urls = super(RegistrationAdmin, self).get_urls()
        return [
            url(r'^repopulate_registration_metrics/$',
                self.admin_site.admin_view(self.repopulate_metrics),
                name='repopulate_registration_metrics'),
        ] + urls

    def repopulate_metrics(self, request):
        context = dict(
            self.admin_site.each_context(request),
            title='Repopulate Metrics',
            opts=self.model._meta,
            form=None
        )
        return TemplateResponse(
            request,
            "admin/registrations/registration/repopulate_metrics.html",
            context)


class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "messageset", "next_sequence_number", "lang",
        "schedule", "created_at", "updated_at"]
    list_filter = ["messageset", "created_at"]
    search_fields = ["identity"]


admin.site.register(Source)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(SubscriptionRequest, SubscriptionRequestAdmin)
