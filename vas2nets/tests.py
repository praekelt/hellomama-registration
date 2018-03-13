from datetime import datetime
import responses
import json

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from mock import patch
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from hellomama_registration import utils
from .models import VoiceCall


def override_get_today():
    return datetime.strptime("20170922", "%Y%m%d")


class APITestCase(TestCase):

    def setUp(self):
        self.normalclient = APIClient()
        utils.get_today = override_get_today


class AuthenticatedAPITestCase(APITestCase):

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()

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


class TestFetchVoiceData(AuthenticatedAPITestCase):

    @responses.activate
    def test_fetch_voice_data(self):
        lines = [
            'BegTime,Shortcode,"Mobile Number",Duration,"Reason"',
            '"2017-09-21 14:22:54",1444,08032311111,30,"No Answer"',
            '"2017-09-21 14:22:57",1444,07037622222,60,"Network failure"',
            '"2017-09-21 16:22:57",1444,08164033333,65,"Network failure"',
        ]

        responses.add(
            responses.GET,
            "%s?report_date=2017-09-21" % (settings.V2N_VOICE_URL),
            status=200,
            body='\n'.join(lines),
            match_querystring=True
        )

        response = self.normalclient.post('/api/v1/fetch_voice_data/',
                                          content_type='application/json')

        self.assertEqual(response.status_code,
                         status.HTTP_202_ACCEPTED)

        self.assertEqual(VoiceCall.objects.all().count(), 3)

        call = VoiceCall.objects.all().order_by('created_at').last()
        self.assertEqual(str(call.created_at), '2017-09-21 15:22:57+00:00')
        self.assertEqual(call.shortcode, "1444")
        self.assertEqual(call.msisdn, "08164033333")
        self.assertEqual(call.duration, 65)
        self.assertEqual(call.reason, "Network failure")

    @responses.activate
    def test_fetch_history(self):

        line_data = {
            '2017-09-25': [
                'BegTime,Shortcode,"Mobile Number",Duration,"Reason"',
                '"2017-09-25 14:22:54",1444,08032311111,30,"No Answer"',
                '"2017-09-25 14:22:57",1444,07037622222,60,"Network failure"',
                '"2017-09-25 16:22:57",1444,08164033333,65,"Network failure"',
            ],
            '2017-09-26': [
                'BegTime,Shortcode,"Mobile Number",Duration,"Reason"',
                '"2017-09-26 14:22:54",1444,08032311111,30,"No Answer"',
                '"2017-09-26 14:22:57",1444,07037622222,60,"Network failure"',
                '"2017-09-26 16:22:57",1444,08164033333,65,"Network failure"',
            ],
            '2017-09-27': [
                'BegTime,Shortcode,"Mobile Number",Duration,"Reason"',
                '"2017-09-27 14:22:54",1444,08032311111,30,"No Answer"',
                '"2017-09-27 14:22:57",1444,07037622222,60,"Network failure"',
                '"2017-09-27 16:22:57",1444,08164033333,65,"Network failure"',
            ]
        }

        for key, lines in line_data.items():
            responses.add(
                responses.GET,
                "%s?report_date=%s" % (settings.V2N_VOICE_URL, key),
                status=200,
                body='\n'.join(lines),
                match_querystring=True
            )

        response = self.normalclient.post(
            '/api/v1/fetch_voice_data/?start=2017-09-25&end=2017-09-27',
            content_type='application/json')

        self.assertEqual(response.status_code,
                         status.HTTP_202_ACCEPTED)

        self.assertEqual(VoiceCall.objects.all().count(), 9)

        call = VoiceCall.objects.all().order_by('created_at').first()
        self.assertEqual(str(call.created_at), '2017-09-25 13:22:54+00:00')
        self.assertEqual(call.shortcode, "1444")
        self.assertEqual(call.msisdn, "08032311111")
        self.assertEqual(call.duration, 30)
        self.assertEqual(call.reason, "No Answer")

        call = VoiceCall.objects.all().order_by('created_at').last()
        self.assertEqual(str(call.created_at), '2017-09-27 15:22:57+00:00')
        self.assertEqual(call.shortcode, "1444")
        self.assertEqual(call.msisdn, "08164033333")
        self.assertEqual(call.duration, 65)
        self.assertEqual(call.reason, "Network failure")


class TestSyncWelcomeAudio(AuthenticatedAPITestCase):

    @responses.activate
    @patch('sftpclone.sftpclone.SFTPClone.__init__')
    @patch('sftpclone.sftpclone.SFTPClone.run')
    def test_sync_welcome_audio(self, sftp_run_mock, sftp_mock):

        sftp_run_mock.return_value = None
        sftp_mock.return_value = None

        response = self.normalclient.post('/api/v1/sync_welcome_audio/',
                                          content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        sftp_mock.assert_called_with(
            '{}/registrations/static/audio/registration/'.format(
                settings.BASE_DIR),
            'test:secret@localhost:test_directory', port=2222, delete=False)


class TestResendLastMessage(AuthenticatedAPITestCase):

    def mock_identity_lookup(self, msisdn, identity_id, results=None):
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/search/?details__addresses__msisdn=%s' % msisdn,  # noqa
            json={
                "next": None, "previous": None,
                "results": results or []
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

    def mock_get_subscriptions(self, identity, results=None):
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/?active=True&identity={}'.format(identity),  # noqa
            json={
                "next": None,
                "previous": None,
                "results": results or [],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

    def mock_resend_subscription(self, subscription_id):
        responses.add(
            responses.POST,
            'http://localhost:8005/api/v1/subscriptions/{}/resend'.format(
                subscription_id),
            status=202, content_type='application/json',
        )

    @responses.activate
    def test_resend_last_message(self):
        """
        If a resend request is received it should request a resend from the
        stage based messenger for each active subscription that is not
        completed or in the wrong process status.
        """

        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"
        identity_results = [{
            "id": mother_id,
            "details": {
                "addresses": {
                    'msisdn': {
                        '+2347031221927'.replace('%2B', '+'): {'default': True}
                    }
                }
            }
        }]
        self.mock_identity_lookup("%2B2347031221927", mother_id,
                                  identity_results)

        results = [{
            "id": "test_id",
            "messageset": 1,
            "active": True,
            "completed": False,
            "process_status": 0,
            "next_sequence_number": 1,
        }, {
            "id": "test_id2",
            "messageset": 1,
            "active": True,
            "completed": True,
            "process_status": 0,
            "next_sequence_number": 1,
        }, {
            "id": "test_id3",
            "messageset": 1,
            "active": True,
            "completed": False,
            "process_status": 2,
            "next_sequence_number": 1,
        }]
        self.mock_get_subscriptions(mother_id, results=results)
        self.mock_resend_subscription("test_id")

        response = self.normalclient.post(
            '/api/v1/resend_last_message/',
            json.dumps({"msisdn": "07031221927"}),
            content_type='application/json')

        self.assertEqual(response.json().get('accepted'), True)
        self.assertEqual(response.json().get('resent_count'), 1)

    @responses.activate
    def test_resend_last_message_no_identity(self):
        """
        If a resend request is received and no identity is found it should
        raise an appropraite error.
        """

        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"
        self.mock_identity_lookup("%2B2347031221928", mother_id)

        response = self.normalclient.post(
            '/api/v1/resend_last_message/',
            json.dumps({"msisdn": "07031221928"}),
            content_type='application/json')

        self.assertEqual(response.json().get('accepted'), False)
        self.assertEqual(response.json().get('reason'),
                         "Cannot find identity for MSISDN +2347031221928")

    @responses.activate
    def test_resend_last_message_no_msisdn(self):
        """
        If a resend request is received and no msisdn is received it should
        raise an appropraite error.
        """

        response = self.normalclient.post(
            '/api/v1/resend_last_message/',
            json.dumps({"to_addr": "07031221928"}),
            content_type='application/json')

        self.assertEqual(response.json().get('accepted'), False)
        self.assertEqual(response.json().get('reason'),
                         "Missing field: 'msisdn'")
