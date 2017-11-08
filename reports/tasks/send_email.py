import os

from .base import BaseTask

from django.core.mail import EmailMessage

from reports.models import ReportTaskStatus


class SendEmail(BaseTask):

    def run(self, **kwargs):
        subject = kwargs['subject']
        sender = kwargs['sender']
        recipients = kwargs['recipients']
        file_location = kwargs['file_location']
        file_name = kwargs['file_name']
        task_status_id = kwargs['task_status_id']

        email = EmailMessage(subject, '', sender, recipients)
        with open(file_location, 'rb') as fp:
            email.attach(file_name, fp.read(), 'application/vnd.ms-excel')
        email.send()

        task_status = ReportTaskStatus.objects.get(id=task_status_id)
        task_status.status = ReportTaskStatus.DONE
        task_status.save()

        try:
            os.remove(file_location)
        except OSError:
            pass
