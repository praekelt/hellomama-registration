from django.contrib import admin

from .models import VoiceCall


class VoiceCallAdmin(admin.ModelAdmin):
    list_display = ['id', 'shortcode', 'created_at', 'msisdn', 'duration',
                    'reason']

admin.site.register(VoiceCall, VoiceCallAdmin)
