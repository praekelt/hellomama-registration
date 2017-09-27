import csv
import requests

from django.conf import settings
from celery.task import Task

from .models import VoiceCall


class FetchVoiceData(Task):

    def get_data(self, date):
        url = "%s?report_date=%s" % (settings.V2N_VOICE_URL, date)

        content = requests.get(url).content.decode('utf-8')

        return list(csv.reader(content.splitlines(), delimiter=','))[1:]

    def run(self, date, **kwargs):
        data = self.get_data(date)
        for row in data:
            VoiceCall.objects.create(
                created_at=row[0],
                msisdn=row[2],
                duration=row[3],
                reason=row[4]
            )

fetch_voice_data = FetchVoiceData()
