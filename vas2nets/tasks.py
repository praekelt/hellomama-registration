import csv
import requests
import pytz

from django.conf import settings
from django.utils.dateparse import parse_datetime
from celery.task import Task

from .models import VoiceCall


class FetchVoiceData(Task):

    def get_data(self, date):
        url = "%s?report_date=%s" % (settings.V2N_VOICE_URL, date)

        content = requests.get(url, stream=True)

        return csv.DictReader(content.iter_lines())

    def run(self, date, **kwargs):
        data = self.get_data(date)

        localtz = pytz.timezone('Africa/Lagos')

        for row in data:
            VoiceCall.objects.get_or_create(
                created_at=localtz.localize(parse_datetime(row['BegTime'])),
                shortcode=row['Shortcode'],
                msisdn=row['Mobile Number'],
                duration=row['Duration'],
                reason=row['Reason']
            )


fetch_voice_data = FetchVoiceData()
