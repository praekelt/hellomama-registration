import json
import pytz

try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import ReportTaskStatus


class ViewTest(TestCase):
    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()
        self.otherclient = APIClient()

        # Admin User setup
        self.adminusername = 'testadminuser'
        self.adminpassword = 'testadminpass'
        self.adminuser = User.objects.create_superuser(
            self.adminusername,
            'testadminuser@example.com',
            self.adminpassword)
        admintoken = Token.objects.create(user=self.adminuser)
        self.admintoken = admintoken.key
        self.adminclient.credentials(
            HTTP_AUTHORIZATION='Token ' + self.admintoken)

        # Normal User setup
        self.normalusername = 'testnormaluser'
        self.normalpassword = 'testnormalpass'
        self.normaluser = User.objects.create_user(
            self.normalusername,
            'testnormaluser@example.com',
            self.normalpassword)
        normaltoken = Token.objects.create(user=self.normaluser)
        self.normaltoken = normaltoken.key
        self.normalclient.credentials(
            HTTP_AUTHORIZATION='Token ' + self.normaltoken)


class ReportsViewTest(ViewTest):
    def midnight(self, timestamp):
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=pytz.timezone(settings.TIME_ZONE))

    def test_get_returns_list_of_reports(self):
        response = self.normalclient.get('/api/v1/reports/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue(isinstance(response.data['reports'], dict))

    @mock.patch("reports.tasks.detailed_report.generate_report.apply_async")
    def test_auth_required(self, mock_generation):
        data = {}

        # Without authentication
        request = self.otherclient.post('/api/v1/reports/', json.dumps(data),
                                        content_type='application/json')
        self.assertEqual(request.status_code, 401,
                         "Authentication should be required.")

        # With authenticated
        request = self.normalclient.post('/api/v1/reports/', json.dumps(data),
                                         content_type='application/json')
        self.assertEqual(request.status_code, 202)

    @mock.patch("reports.tasks.detailed_report.generate_report.apply_async")
    def test_post_successful(self, mock_generation):
        data = {
            'start_date': '2016-01-01',
            'end_date': '2016-02-01',
            'email_to': ['foo@example.com'],
            'email_subject': 'The Email Subject'
        }

        request = self.adminclient.post('/api/v1/reports/',
                                        json.dumps(data),
                                        content_type='application/json')
        self.assertEqual(request.status_code, 202)
        self.assertEqual(request.data, {"report_generation_requested": True})

        task_status = ReportTaskStatus.objects.last()

        mock_generation.assert_called_once_with(kwargs={
            "start_date": '2016-01-01',
            "end_date": '2016-02-01',
            "email_recipients": ['foo@example.com'],
            "email_sender": settings.DEFAULT_FROM_EMAIL,
            "email_subject": 'The Email Subject',
            "task_status_id": task_status.id})

        self.assertEqual(task_status.status, ReportTaskStatus.PENDING)

    def test_response_on_incorrect_date_format(self):
        data = {
            'start_date': '2016:01:01',
            'end_date': '2016:02:01',
            'email_to': ['foo@example.com'],
            'email_subject': 'The Email Subject'
        }

        request = self.adminclient.post('/api/v1/reports/',
                                        json.dumps(data),
                                        content_type='application/json')
        self.assertEqual(request.status_code, 400)
        self.assertEqual(request.data, {
            'start_date':
                ["time data '2016:01:01' does not match format '%Y-%m-%d'"],
            'end_date':
                ["time data '2016:02:01' does not match format '%Y-%m-%d'"]
            })

    def test_report_task_view(self):
        """
        This view should only return the last 10 items.
        """
        for i in range(15):
            ReportTaskStatus.objects.create(**{
                "start_date": self.midnight(datetime.strptime('2016-01-01',
                                                              '%Y-%m-%d')),
                "end_date": self.midnight(datetime.strptime('2016-02-01',
                                                            '%Y-%m-%d')),
                "email_subject": 'The Email Subject',
                "file_size": 12343,
                "status": ReportTaskStatus.PENDING
            })
        request = self.normalclient.get('/api/v1/reporttasks/')
        results = json.loads(request.content.decode('utf8'))['results']

        self.assertEqual(len(results), 10)
        self.assertEqual(results[0]['status'], 'Pending')
        self.assertEqual(results[0]['email_subject'], 'The Email Subject')
        self.assertEqual(results[0]['file_size'], 12343)
        self.assertEqual(results[0]['start_date'], '2016-01-01 00:00:00+00:00')
        self.assertEqual(results[0]['end_date'], '2016-02-01 00:00:00+00:00')
        self.assertEqual(request.status_code, 200)


class MSISDNMessagesReportViewTest(ViewTest):
    celery_method = ('reports.tasks.msisdn_message_report.'
                     'generate_msisdn_message_report.apply_async')

    @mock.patch(celery_method)
    def test_creates_task_status(self, celery_method_patch):
        response = self.normalclient.post('/api/v1/reports/msisdn-messages/',
                                          json.dumps({
                                            'start_date': '2017-09-01',
                                            'end_date': '2018-09-01'}),
                                          content_type='application/json')
        report_task_statuses = ReportTaskStatus.objects.all()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(report_task_statuses), 1)
        self.assertEqual(report_task_statuses.first().start_date, '2017-09-01')
        self.assertEqual(report_task_statuses.first().end_date, '2018-09-01')
        self.assertEqual(report_task_statuses.first().status, 'P')

    @mock.patch(celery_method)
    def test_creates_background_task(self, celery_method_patch):
        self.normalclient.post('/api/v1/reports/msisdn-messages/',
                               json.dumps({'start_date': '2017-09-01',
                                           'end_date': '2018-09-01',
                                           'msisdn_list': ['+2345565942365']}),
                               content_type='application/json')
        report_task_status = ReportTaskStatus.objects.first()

        celery_method_patch.assert_called_once_with(kwargs={
            "start_date": '2017-09-01',
            "end_date": '2018-09-01',
            'msisdns': ['+2345565942365'],
            'task_status_id': report_task_status.id,
            'email_recipients': [],
            'email_sender': settings.DEFAULT_FROM_EMAIL,
            'email_subject': 'HelloMama Generated Report'
        })

    @mock.patch(celery_method)
    def test_forwards_email_details_to_task(self, celery_method_patch):
        self.normalclient.post('/api/v1/reports/msisdn-messages/',
                               json.dumps({'start_date': '2017-09-01',
                                           'end_date': '2018-09-01',
                                           'msisdn_list': ['+2344263256918'],
                                           'email_to': ['foo@example.com'],
                                           'email_from': 'bar@example.com',
                                           'email_subject': 'Cohort report'}),
                               content_type='application/json')
        report_task_status = ReportTaskStatus.objects.first()

        celery_method_patch.assert_called_once_with(kwargs={
            "start_date": '2017-09-01',
            "end_date": '2018-09-01',
            'msisdns': ['+2344263256918'],
            'task_status_id': report_task_status.id,
            'email_recipients': ['foo@example.com'],
            'email_sender': 'bar@example.com',
            'email_subject': 'Cohort report'
        })

    def test_raises_400_for_invalid_msisdns(self):
        response = self.normalclient.post(
            '/api/v1/reports/msisdn-messages/',
            json.dumps({'start_date': '2017-09-01', 'end_date': '2018-09-01',
                        'msisdn_list': ['+2345565']}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {
            'msisdn_list': ["Invalid value for: msisdn_list. Msisdns must "
                            "only contain digits, be 14 characters long and "
                            "contain the prefix '+234'"]})

        response = self.normalclient.post(
            '/api/v1/reports/msisdn-messages/',
            json.dumps({'start_date': '2017-09-01', 'end_date': '2018-09-01',
                        'msisdn_list': ['+1234265556585']}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {
            'msisdn_list': ["Invalid value for: msisdn_list. Msisdns must "
                            "only contain digits, be 14 characters long and "
                            "contain the prefix '+234'"]})

        response = self.normalclient.post(
            '/api/v1/reports/msisdn-messages/',
            json.dumps({'start_date': '2017-09-01', 'end_date': '2018-09-01',
                        'msisdn_list': ['+234sdk83dfs61']}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {
            'msisdn_list': ["Invalid value for: msisdn_list. Msisdns must "
                            "only contain digits, be 14 characters long and "
                            "contain the prefix '+234'"]})
