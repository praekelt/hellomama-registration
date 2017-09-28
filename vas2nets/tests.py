from datetime import datetime
import responses

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
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
