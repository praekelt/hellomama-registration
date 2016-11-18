from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.conf.urls import url
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from hellomama_registration.utils import get_available_metrics, get_identity
from .models import Source, Registration, SubscriptionRequest
from .tasks import repopulate_metrics
from uniqueids.models import Record


class RepopulateMetricsForm(forms.Form):
    amqp_url = forms.CharField(
        label='AMQP URL', initial='amqp://guest:guest@localhost:5672/%2F',
        widget=forms.TextInput(attrs={'size': 80}))
    prefix = forms.CharField(
        label='Metric Name Prefix', initial='', required=False,
        widget=forms.TextInput(attrs={'size': 80}))
    metric_names = forms.MultipleChoiceField(choices=[])
    graphite_retentions = forms.CharField(
        label='Graphite Retentions', initial='1m:1d,5m:1y,1h:5y',
        widget=forms.TextInput(attrs={'size': 80}))

    def __init__(self, *args, **kwargs):
        super(RepopulateMetricsForm, self).__init__(*args, **kwargs)
        # We populate the choices here because they rely on database values,
        # so they could change between import and form render.
        metrics = get_available_metrics()
        self.fields['metric_names'].choices = [(m, m) for m in metrics]
        self.fields['metric_names'].initial = metrics


class RegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "id", "stage", "validated", "mother_id", "source",
        "created_at", "updated_at", "created_by", "updated_by"]
    list_filter = ["source", "validated", "created_at"]
    search_fields = ["mother_id", "to_addr"]
    actions = ["regenerate_personnel_code"]

    def get_urls(self):
        urls = super(RegistrationAdmin, self).get_urls()
        return [
            url(r'^repopulate_registration_metrics/$',
                self.admin_site.admin_view(self.repopulate_metrics),
                name='registrations_registration_repopulate_metrics'),
        ] + urls

    def repopulate_metrics(self, request):

        if request.method == 'POST':
            form = RepopulateMetricsForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                repopulate_metrics.delay(
                    data['amqp_url'], data['prefix'], data['metric_names'],
                    data['graphite_retentions'])
                messages.success(request, 'Metrics repopulation started')
                return redirect('admin:registrations_registration_changelist')
        else:
            form = RepopulateMetricsForm()
        context = dict(
            self.admin_site.each_context(request),
            title='Repopulate Metrics',
            opts=self.model._meta,
            form=form,
            adminform=helpers.AdminForm(
                form, [(None, {'fields': form.base_fields})],
                self.get_prepopulated_fields(request)),
        )
        return TemplateResponse(
            request,
            "admin/registrations/registration/repopulate_metrics.html",
            context)

    def regenerate_personnel_code(self, request, queryset):
        created = 0
        skipped = 0
        for reg in queryset:
            identity = get_identity(reg.mother_id)
            if identity.get("detail") == "Not found.":
                skipped += 1
                continue
            print identity
            current_code = identity['details'].get("personnel_code", None)
            if current_code:
                Record.objects.create(
                    identity=identity['id'], write_to="personnel_code",
                    length=len(current_code), created_by=request.user)
                created += 1
            else:
                skipped += 1
        if created == 1:
            created_text = "%s Registration was" % created
        else:
            created_text = "%s Registrations were" % created
        if skipped == 1:
            skipped_text = "%s Registration was" % skipped
        else:
            skipped_text = "%s Registrations were" % skipped
        self.message_user(
            request, "%s successfully changed. %s skipped because they are "
            "not a HCW." % (created_text, skipped_text))

    regenerate_personnel_code.short_description = "Change personnel code and "\
        "SMS"


class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "messageset", "next_sequence_number", "lang",
        "schedule", "created_at", "updated_at"]
    list_filter = ["messageset", "created_at"]
    search_fields = ["identity"]


admin.site.register(Source)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(SubscriptionRequest, SubscriptionRequestAdmin)
