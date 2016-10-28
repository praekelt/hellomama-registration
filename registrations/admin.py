from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.conf.urls import url
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from hellomama_registration.utils import get_available_metrics
from .models import Source, Registration, SubscriptionRequest
from .tasks import repopulate_metrics


class RepopulateMetricsForm(forms.Form):
    amqp_url = forms.CharField(
        label='AMQP URL', initial='amqp://guest:guest@localhost:5672/%2F',
        widget=forms.TextInput(attrs={'size': 80}))
    prefix = forms.CharField(
        label='Metric Name Prefix', initial='',
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


class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "messageset", "next_sequence_number", "lang",
        "schedule", "created_at", "updated_at"]
    list_filter = ["messageset", "created_at"]
    search_fields = ["identity"]


admin.site.register(Source)
admin.site.register(Registration, RegistrationAdmin)
admin.site.register(SubscriptionRequest, SubscriptionRequestAdmin)
