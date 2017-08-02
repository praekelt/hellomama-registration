import json
import pytz
import responses
import os

try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from openpyxl import load_workbook
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_hooks.models import model_saved

from registrations.models import (
    Registration, registration_post_save, fire_created_metric,
    fire_unique_operator_metric, fire_message_type_metric, fire_source_metric,
    fire_receiver_type_metric, fire_language_metric, fire_state_metric,
    fire_role_metric)
from .utils import parse_cursor_params, generate_random_filename
from .tasks import generate_report


class mockobj(object):
    @classmethod
    def choice(cls, li):
        return li[0]


@override_settings(
    IDENTITY_STORE_URL='http://idstore.example.com/',
    IDENTITY_STORE_TOKEN='idstoretoken',
    MESSAGE_SENDER_URL='http://ms.example.com/',
    MESSAGE_SENDER_TOKEN='mstoken',
    STAGE_BASED_MESSAGING_URL='http://sbm.example.com/',
    STAGE_BASED_MESSAGING_TOKEN='sbmtoken')
class GenerateReportTest(TestCase):
    def setUp(self):
        def has_listeners(class_name):
            return post_save.has_listeners(class_name)
        assert has_listeners(Registration), (
            "Registration model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=registration_post_save,
                             sender=Registration)
        post_save.disconnect(receiver=fire_created_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_source_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_unique_operator_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_message_type_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_receiver_type_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_language_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_state_metric,
                             sender=Registration)
        post_save.disconnect(receiver=fire_role_metric,
                             sender=Registration)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(Registration), (
            "Registration model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def tearDown(self):
        def has_listeners(class_name):
            return post_save.has_listeners(class_name)
        assert not has_listeners(Registration), (
            "Registration model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(receiver=registration_post_save,
                          sender=Registration)
        post_save.connect(receiver=fire_created_metric,
                          sender=Registration)
        post_save.connect(receiver=fire_source_metric,
                          sender=Registration)
        post_save.connect(receiver=fire_unique_operator_metric,
                          sender=Registration)
        post_save.connect(receiver=fire_language_metric,
                          sender=Registration)
        post_save.connect(receiver=fire_state_metric,
                          sender=Registration)
        post_save.connect(receiver=fire_role_metric,
                          sender=Registration)

        post_save.connect(receiver=model_saved,
                          dispatch_uid='instance-saved-hook')

        try:
            with mock.patch('random.choice', mockobj.choice):
                filename = generate_random_filename()
                os.remove(filename)
        except OSError:
            pass

    def assertSheetRow(self, file_name, sheet_name, row_number, expected):
        wb = load_workbook(file_name)
        sheet = wb[sheet_name]
        rows = list(sheet.rows)
        self.assertEqual(
            [cell.value for cell in rows[row_number]],
            expected)

    def test_parse_cursor_params(self):
        cursor = ("https://example"
                  "?created_after=2010-01-01T00%3A00%3A00%2B00%3A00"
                  "&created_before=2016-10-17T00%3A00%3A00%2B00%3A00"
                  "&limit=1000&offset=1000")
        params = parse_cursor_params(cursor)
        self.assertEqual(params['created_after'], '2010-01-01T00:00:00+00:00')
        self.assertEqual(params['created_before'], '2016-10-17T00:00:00+00:00')
        self.assertEqual(params['limit'], '1000')
        self.assertEqual(params['offset'], '1000')

    def add_registrations(self, num=1):
        for i in range(num):
            Registration.objects.create(
                created_at='2016-01-02 00:00:00+00:00', data={
                    'operator_id': 'operator_id',
                    'receiver_id': 'receiver_id',
                    'gravida': 'gravida',
                    'msg_type': 'msg_type',
                    'last_period_date': 'last_period_date',
                    'language': 'language',
                    'msg_receiver': 'msg_receiver',
                    'voice_days': 'voice_days',
                    'voice_times': 'voice_times',
                    'preg_week': 'preg_week',
                    'reg_type': 'reg_type',
                },
                source_id=1
            )

    def add_identity_callback(self, identity='operator_id'):
        responses.add(
            responses.GET,
            'http://idstore.example.com/identities/{}/'.format(identity),
            json={
                'identity': identity,
                'details': {
                    'personnel_code': 'personnel_code',
                    'facility_name': 'facility_name',
                    'default_addr_type': 'msisdn',
                    'receiver_role': 'role',
                    'state': 'state',
                    'addresses': {
                        'msisdn': {
                            '+2340000000000': {}
                        }
                    }
                }
            },
            status=200,
            content_type='application/json')

    def add_blank_subscription_callback(self, next_='?foo=bar'):
        if next_:
            next_ = 'http://sbm.example.com/subscriptions/{}'.format(next_)

        responses.add(
            responses.GET,
            ("http://sbm.example.com/subscriptions/?"
             "created_before=2016-02-01T23%3A59%3A59.999999%2B00%3A00"),
            match_querystring=True,
            json={
                'count': 0,
                'next': next_,
                'results': [],
            },
            status=200,
            content_type='application/json')

    def add_subscriptions_callback(self, path='?foo=bar', num=1):
        subscriptions = [{
            'lang': 'eng_NG',
            'created_at': '2016-11-22T08:12:45.343829Z',
            'messageset': 4,
            'schedule': 5,
            'url': 'url',
            'completed': False,
            'initial_sequence_number': 1,
            'updated_at': '2016-11-22T08:12:52.411545Z',
            'version': 1,
            'next_sequence_number': 1,
            'process_status': 0,
            'active': True,
            'id': '10176584-2a47-42b6-b9f3-a3a98070f35e',
            'identity': '17cf37cf-edd6-4634-88e3-f793575f7e3a',
            'metadata': {
                'scheduler_schedule_id':
                    'a64d153f-1515-42c1-997a-9a3444c916fc'
            }
        }] * num

        responses.add(
            responses.GET,
            'http://sbm.example.com/subscriptions/{}'.format(path),
            match_querystring=True,
            json={
                'count': num,
                'next': None,
                'results': subscriptions,
            },
            status=200,
            content_type='application/json')

    def add_blank_outbound_callback(self, next_='?foo=bar'):
        if next_:
            next_ = 'http://ms.example.com/outbound/{}'.format(next_)

        responses.add(
            responses.GET,
            ("http://ms.example.com/outbound/?"
             "before=2016-02-01T23%3A59%3A59.999999%2B00%3A00"
             "&after=2016-01-01T00%3A00%3A00%2B00%3A00"),
            match_querystring=True,
            json={
                'count': 0,
                'next': next_,
                'results': [],
            },
            status=200,
            content_type='application/json')

    def add_outbound_callback(
            self, num=1, metadata={}, options=(('addr', ''), )):
        outbounds = []

        for i in range(0, num):
            for option in options:
                outbounds.append({
                    'to_addr': option[0],
                    'to_identity': option[1],
                    'content': 'content',
                    'delivered': True if i % 2 == 0 else False,
                    'created_at': '2016-01-01T10:30:21.{}Z'.format(i),
                    'metadata': metadata
                })

        responses.add(
            responses.GET,
            'http://ms.example.com/outbound/?foo=bar',
            match_querystring=True,
            json={
                'count': num,
                'next': None,
                'results': outbounds,
            },
            status=200,
            content_type='application/json')

    def add_messageset_callback(self):
        responses.add(
            responses.GET,
            'http://sbm.example.com/messageset/4/',
            json={
                'created_at': '2016-06-22T10:30:21.186435Z',
                'short_name': 'prebirth.mother.audio.10_42.tue_thu.9_11',
                'next_set': 11,
                'notes': '',
                'updated_at': '2016-09-13T13:01:32.591754Z',
                'default_schedule': 5,
                'content_type': 'audio',
                'id': 4
            },
            status=200,
            content_type='application/json')

    def add_blank_optouts_callback(self, next_='?foo=bar'):
        if next_:
            next_ = 'http://idstore.example.com/optouts/search/{}'.format(
                next_)

        responses.add(
            responses.GET,
            ("http://idstore.example.com/optouts/search/?"
             "created_at__lte=2016-02-01T23%3A59%3A59.999999%2B00%3A00&"
             "created_at__gte=2016-01-01T00%3A00%3A00%2B00%3A00"),
            match_querystring=True,
            json={
                'count': 0,
                'next': next_,
                'results': [],
            },
            status=200,
            content_type='application/json')

    def add_optouts_callback(self, path='?foo=bar', num=1):
        optouts = [{
            "id": "e5210c99-8d8a-40f1-8e7f-8a66c4de9e29",
            "optout_type": "stop",
            "identity": "8311c23d-f3c4-4cab-9e20-5208d77dcd1b",
            "address_type": "msisdn",
            "address": "+1234",
            "request_source": "testsource",
            "requestor_source_id": "1",
            "reason": "Test reason",
            "created_at": "2017-01-27T10:00:06.354178Z"
        }] * num

        responses.add(
            responses.GET,
            'http://idstore.example.com/optouts/search/{}'.format(path),
            match_querystring=True,
            json={
                'count': num,
                'next': None,
                'results': optouts,
            },
            status=200,
            content_type='application/json')

    def midnight(self, timestamp):
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=pytz.timezone(settings.TIME_ZONE))

    def trigger_report_generation(self):
        with mock.patch('random.choice', mockobj.choice):
            filename = generate_random_filename()

            generate_report.apply_async(kwargs={
                'start_date': self.midnight(datetime.strptime('2016-01-01',
                                                              '%Y-%m-%d')),
                'end_date': self.midnight(datetime.strptime('2016-02-01',
                                                            '%Y-%m-%d')),
                'email_recipients': ['foo@example.com'],
                'email_subject': 'The Email Subject'})

            return filename

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_email(self, mock_remove):
        """
        Generating a report should create an email with the correct address,
        subject, and attachment.
        """
        self.add_blank_subscription_callback(next_=None)
        self.add_blank_outbound_callback(next_=None)
        self.add_blank_optouts_callback(next_=None)
        self.trigger_report_generation()
        [report_email] = mail.outbox
        self.assertEqual(report_email.subject, 'The Email Subject')
        (file_name, data, mimetype) = report_email.attachments[0]
        self.assertEqual('report-2016-01-01-to-2016-02-01.xlsx', file_name)

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_registrations(self, mock_remove):
        """
        When generating a report, the first tab should be a list of
        registrations with the relevant registration details.
        """
        # Add Registrations
        self.add_registrations()
        Registration.objects.all().update(created_at='2016-02-01 01:00:00')

        # HCW Identity
        self.add_identity_callback()

        # Receiver Identity
        self.add_identity_callback('receiver_id')

        # Subscriptions, first page, just returns empty results to make sure
        # we're actually paging through the results sets using the `next`
        # parameter
        self.add_blank_subscription_callback(next_=None)

        self.add_subscriptions_callback()

        self.add_messageset_callback()

        self.add_identity_callback('17cf37cf-edd6-4634-88e3-f793575f7e3a')

        self.add_blank_outbound_callback(next_=None)

        self.add_outbound_callback()

        # No opt outs, we're not testing optout by subscription
        self.add_blank_optouts_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert headers are set
        self.assertSheetRow(
            tmp_file, 'Registrations by date', 0,
            [
                'MSISDN',
                'Created',
                'gravida',
                'msg_type',
                'last_period_date',
                'language',
                'msg_receiver',
                'voice_days',
                'Voice_times',
                'preg_week',
                'reg_type',
                'Personnel_code',
                'Facility',
                'Cadre',
                'State',
            ])

        # Assert 1 row is written
        self.assertSheetRow(
            tmp_file, 'Registrations by date', 1,
            [
                '+2340000000000',
                '2016-02-01T01:00:00+00:00',
                'gravida',
                'msg_type',
                'last_period_date',
                'language',
                'msg_receiver',
                'voice_days',
                'voice_times',
                'preg_week',
                'reg_type',
                'personnel_code',
                'facility_name',
                None,
                'state',
            ])

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_health_worker_registrations(self, mock_remove):
        """
        When generating a report, the second tab should be registrations per
        health worker, and it should have the correct information.
        """
        # Add Registrations and correct date, 2 registrations for 1 operator
        self.add_registrations(num=2)
        Registration.objects.all().update(created_at='2016-01-02 00:00:00')

        # Identity for hcw
        self.add_identity_callback('operator_id')

        # identity for receiver, for first report
        self.add_identity_callback('receiver_id')

        # Subscriptions, first page, just returns empty results to make sure
        # we're actually paging through the results sets using the `next`
        # parameter
        self.add_blank_subscription_callback(next_=None)

        self.add_subscriptions_callback(num=2)

        self.add_messageset_callback()

        self.add_identity_callback('17cf37cf-edd6-4634-88e3-f793575f7e3a')

        self.add_blank_outbound_callback(next_=None)

        self.add_outbound_callback()

        # No opt outs, we're not testing optout by subscription
        self.add_blank_optouts_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert headers are set
        self.assertSheetRow(
            tmp_file, 'Health worker registrations', 0,
            [
                'Unique Personnel Code',
                'Facility',
                'State',
                'Cadre',
                'Number of Registrations',
            ])

        # Assert 1 row is written
        self.assertSheetRow(
            tmp_file, 'Health worker registrations', 1,
            [
                'personnel_code',
                'facility_name',
                'state',
                'role',
                2,
            ])

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_enrollments(self, mock_remove):
        """
        When generating a report, the third tab should be enrollments,
        and it should have the correct information.
        """
        # Add Registrations, 2 registrations for 1 operator
        self.add_registrations(num=2)

        # Identity for hcw
        self.add_identity_callback('operator_id')

        # identity for receiver, for first report
        self.add_identity_callback('receiver_id')

        # Subscriptions, first page, just returns empty results to make sure
        # we're actually paging through the results sets using the `next`
        # parameter
        self.add_blank_subscription_callback()

        self.add_subscriptions_callback(num=2)

        self.add_messageset_callback()

        self.add_identity_callback('17cf37cf-edd6-4634-88e3-f793575f7e3a')

        self.add_blank_outbound_callback(next_=None)

        self.add_outbound_callback()

        # No opt outs, we're not testing optout by subscription
        self.add_blank_optouts_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert headers are set
        self.assertSheetRow(
            tmp_file, 'Enrollments', 0,
            [
                'Message set',
                'Roleplayer',
                'Total enrolled',
                'Enrolled in period',
                'Enrolled and opted out in period',
                'Enrolled and completed in period',
            ])

        # Assert 1 row is written
        self.assertSheetRow(
            tmp_file, 'Enrollments', 1,
            ['prebirth', 'role', 2, 2, 0, 0])

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_sms_per_msisdn(self, mock_remove):
        """
        When generating a report, the fourth tab should be SMS delivery per
        MSISDN, and it should have the correct information.
        """
        # Add Registrations, 2 registrations for 1 operator
        self.add_registrations(num=2)

        # Identity for hcw
        self.add_identity_callback('operator_id')

        # identity for receiver, for first report
        self.add_identity_callback('receiver_id')

        # Subscriptions, first page, just returns empty results to make sure
        # we're actually paging through the results sets using the `next`
        # parameter
        self.add_blank_subscription_callback()

        self.add_subscriptions_callback()

        self.add_messageset_callback()

        self.add_identity_callback('17cf37cf-edd6-4634-88e3-f793575f7e3a')

        self.add_blank_outbound_callback()

        # Create 4 outbounds with to_addr populated and 4 with to_identity
        self.add_outbound_callback(
            num=4, options=(('+2340000001111', ''), ('', 'receiver_id')))

        # No opt outs, we're not testing optout by subscription
        self.add_blank_optouts_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert headers are set
        self.assertSheetRow(
            tmp_file, 'SMS delivery per MSISDN', 0,
            [
                'MSISDN',
                'SMS 1',
                'SMS 2',
                'SMS 3',
                'SMS 4'
            ])

        # Assert 2 rows are written
        self.assertSheetRow(
            tmp_file, 'SMS delivery per MSISDN', 1,
            ['+2340000001111', 'Yes', 'No', 'Yes', 'No'])
        self.assertSheetRow(
            tmp_file, 'SMS delivery per MSISDN', 2,
            ['+2340000000000', 'Yes', 'No', 'Yes', 'No'])

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_obd_delivery_failure(self, mock_remove):
        # Add Registrations, 2 registrations for 1 operator
        self.add_registrations(num=2)

        # Identity for hcw
        self.add_identity_callback('operator_id')

        # identity for receiver, for first report
        self.add_identity_callback('receiver_id')

        # Subscriptions, first page, just returns empty results to make sure
        # we're actually paging through the results sets using the `next`
        # parameter
        self.add_blank_subscription_callback()

        self.add_subscriptions_callback()

        self.add_messageset_callback()

        self.add_identity_callback('17cf37cf-edd6-4634-88e3-f793575f7e3a')

        self.add_blank_outbound_callback()

        self.add_outbound_callback(
            num=40,
            metadata={'voice_speech_url': 'dummy_voice_url'})

        # No opt outs, we're not testing optout by subscription
        self.add_blank_optouts_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert period row
        self.assertSheetRow(
            tmp_file, 'OBD Delivery Failure', 1,
            [
                "In the last period:",
                "2016-01-01 - 2016-02-01",
                None
            ])

        # Check headers
        self.assertSheetRow(
            tmp_file, 'OBD Delivery Failure', 2,
            [
                "OBDs Sent",
                "OBDs failed",
                "Failure rate",
            ]
        )

        # Assert 1 row is written
        self.assertSheetRow(
            tmp_file, 'OBD Delivery Failure', 3,
            [40, 20, '50.00%'])

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_optout_by_date(self, mock_remove):
        # Return no registrations or subscriptions for other reports
        self.add_blank_subscription_callback(next_=None)

        # Optouts, first page no results to make sure that we're paging
        self.add_blank_optouts_callback()
        self.add_optouts_callback()

        # Add identity for optout
        self.add_identity_callback('8311c23d-f3c4-4cab-9e20-5208d77dcd1b')

        # Add subscription result for identity
        self.add_subscriptions_callback(
            path=(
                '?active=False&completed=False&'
                'created_before=2017-01-27T10%3A00%3A06.354178Z&'
                'identity=8311c23d-f3c4-4cab-9e20-5208d77dcd1b')
        )

        # Add messageset for subscription
        self.add_messageset_callback()

        self.add_blank_outbound_callback(next_=None)

        tmp_file = self.trigger_report_generation()

        mock_remove.assert_called_once_with(tmp_file)

        # Assert headers are set
        self.assertSheetRow(
            tmp_file, 'Opt Outs by Date', 0,
            [
                "MSISDN",
                "Optout Date",
                "Request Source",
                "Reason"
            ])

        # Assert row 1 is written
        self.assertSheetRow(
            tmp_file, 'Opt Outs by Date', 1,
            [
                "+1234",
                "2017-01-27T10:00:06.354178Z",
                "testsource",
                "Test reason",
            ])


class ReportsViewTest(TestCase):
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

    def midnight(self, timestamp):
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=pytz.timezone(settings.TIME_ZONE))

    @mock.patch("reports.tasks.generate_report.apply_async")
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

    @mock.patch("reports.tasks.generate_report.apply_async")
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

        mock_generation.assert_called_once_with(kwargs={
            "start_date": '2016-01-01',
            "end_date": '2016-02-01',
            "email_recipients": ['foo@example.com'],
            "email_sender": settings.DEFAULT_FROM_EMAIL,
            "email_subject": 'The Email Subject'})

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
