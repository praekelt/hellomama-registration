import pytz
try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.conf import settings
from django.core import management
from django.test import TestCase
from tempfile import NamedTemporaryFile


class ManagementCommandsTests(TestCase):
    def mk_tempfile(self):
        tmp_file = NamedTemporaryFile(suffix='.xlsx')
        self.addCleanup(tmp_file.close)
        return tmp_file

    def midnight(self, timestamp):
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=pytz.timezone(settings.TIME_ZONE))

    def test_command_requires_output_file(self):
        with self.assertRaises(management.CommandError) as ce:
            management.call_command(
                'generate_reports',
                '--start', '2016-01-01', '--end', '2016-02-01',
                '--email-to', 'foo@example.com',
                '--email-subject', 'The Email Subject')
        self.assertEqual(
            str(ce.exception), "Please specify --output-file.")

    @mock.patch("reports.tasks.generate_report.run")
    def test_command_successful(self, mock_generation):
        tmp_file = self.mk_tempfile()
        management.call_command(
            'generate_reports',
            '--start', '2016-01-01', '--end', '2016-02-01',
            '--output-file', tmp_file.name,
            '--email-to', 'foo@example.com',
            '--email-subject', 'The Email Subject')
        mock_generation.assert_called_once_with(
            output_file=tmp_file.name,
            start_date=self.midnight(datetime.strptime('2016-01-01',
                                                       '%Y-%m-%d')),
            end_date=self.midnight(datetime.strptime('2016-02-01',
                                                     '%Y-%m-%d')),
            email_recipients=['foo@example.com'],
            email_sender=settings.DEFAULT_FROM_EMAIL,
            email_subject='The Email Subject')
