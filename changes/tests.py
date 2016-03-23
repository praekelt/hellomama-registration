import datetime
import json
import responses

from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved

from hellomama_registration import utils
from registrations.models import (Source, Registration, SubscriptionRequest,
                                  registration_post_save)
from .models import Change, change_post_save
from .tasks import implement_action


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()
        self.otherclient = APIClient()
        utils.get_today = override_get_today


class AuthenticatedAPITestCase(APITestCase):

    def _replace_post_save_hooks_change(self):
        def has_listeners():
            return post_save.has_listeners(Change)
        assert has_listeners(), (
            "Change model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=change_post_save,
                             sender=Change)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Change model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_change(self):
        def has_listeners():
            return post_save.has_listeners(Change)
        assert not has_listeners(), (
            "Change model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(change_post_save, sender=Change)

    def _replace_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
        assert has_listeners(), (
            "Registration model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=registration_post_save,
                             sender=Registration)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Registration model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
        assert not has_listeners(), (
            "Registration model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(registration_post_save, sender=Registration)

    def make_source_adminuser(self):
        data = {
            "name": "test_source_adminuser",
            "authority": "hw_full",
            "user": User.objects.get(username='testadminuser')
        }
        return Source.objects.create(**data)

    def make_source_normaluser(self):
        data = {
            "name": "test_source_normaluser",
            "authority": "patient",
            "user": User.objects.get(username='testnormaluser')
        }
        return Source.objects.create(**data)

    def make_change_adminuser(self):
        data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_adminuser_change": "test_adminuser_changed"},
            "source": self.make_source_adminuser()
        }
        return Change.objects.create(**data)

    def make_change_normaluser(self):
        data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_normaluser_change": "test_normaluser_changed"},
            "source": self.make_source_adminuser()
        }
        return Change.objects.create(**data)

    def make_registration_mother_only(self):
        data = {
            "stage": "prebirth",
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "data": {
                "receiver_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
                "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
                "language": "eng_NG",
                "msg_type": "text",
                "gravida": "1",
                "last_period_date": "20150202",
                "msg_receiver": "mother_only",
                # data added during validation
                "reg_type": "hw_pre",
                "preg_week": "15"
            },
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**data)

    def make_registration_friend_only(self):
        data = {
            "stage": "prebirth",
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "data": {
                "receiver_id": "629eaf3c-04e5-4404-8a27-3ab3b811326a",
                "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
                "language": "pcm_NG",
                "msg_type": "text",
                "gravida": "2",
                "last_period_date": "20150302",
                "msg_receiver": "friend_only",
                # data added during validation
                "reg_type": "hw_pre",
                "preg_week": "11"
            },
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**data)

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self._replace_post_save_hooks_change()
        self._replace_post_save_hooks_registration()

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

    def tearDown(self):
        self._restore_post_save_hooks_change()
        self._restore_post_save_hooks_registration()


class TestLogin(AuthenticatedAPITestCase):

    def test_login_normaluser(self):
        """ Test that normaluser can login successfully
        """
        # Setup
        post_auth = {"username": "testnormaluser",
                     "password": "testnormalpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNotNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(
            request.status_code, 200,
            "Status code on /api/token-auth was %s (should be 200)."
            % request.status_code)

    def test_login_adminuser(self):
        """ Test that adminuser can login successfully
        """
        # Setup
        post_auth = {"username": "testadminuser",
                     "password": "testadminpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNotNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(
            request.status_code, 200,
            "Status code on /api/token-auth was %s (should be 200)."
            % request.status_code)

    def test_login_adminuser_wrong_password(self):
        """ Test that adminuser cannot log in with wrong password
        """
        # Setup
        post_auth = {"username": "testadminuser",
                     "password": "wrongpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(request.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_otheruser(self):
        """ Test that an unknown user cannot log in
        """
        # Setup
        post_auth = {"username": "testotheruser",
                     "password": "testotherpass"}
        # Execute
        request = self.otherclient.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(request.status_code, status.HTTP_400_BAD_REQUEST)


class TestChangeAPI(AuthenticatedAPITestCase):

    def test_get_change_adminuser(self):
        # Setup
        change = self.make_change_adminuser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/change/%s/' % change.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_change_normaluser(self):
        # Setup
        change = self.make_change_normaluser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/change/%s/' % change.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_change_adminuser(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/change/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_change_normaluser(self):
        # Setup
        self.make_source_normaluser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.normalclient.post('/api/v1/change/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_normaluser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_change_set_readonly_field(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"},
            "validated": True
        }
        # Execute
        response = self.adminclient.post('/api/v1/change/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)  # Should ignore True post_data
        self.assertEqual(d.data, {"test_key1": "test_value1"})


class TestRegistrationCreation(AuthenticatedAPITestCase):

    def test_make_registration_mother_only(self):
        # Setup
        # Execute
        self.make_registration_mother_only()
        # Test
        d = Registration.objects.last()
        self.assertEqual(d.mother_id, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.data["msg_receiver"], "mother_only")


class TestChangeMessaging(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_only_audio_to_text(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "tue_thu",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=prebirth.mother.audio.10_42.tue_thu.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 4,
                    "short_name": 'prebirth.mother.audio.10_42.tue_thu.9_11',
                    "default_schedule": 6
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/6/',
            json={"id": 6, "day_of_week": "2,4"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.contact, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 4)
        self.assertEqual(d.next_sequence_number, 36)  # week 28 - 18*2
        self.assertEqual(d.lang, "eng_NG")
        self.assertEqual(d.schedule, 6)


class TestChangeBaby(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_only_change_baby(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_baby",
            "data": {},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % change_data[
                "mother_id"],
            json={
                "id": change_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+2345059992222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "linked_to": None,
                    "preferred_msg_type": "audio",
                    "preferred_msg_days": "mon_wed",
                    "preferred_msg_times": "9_11",
                    "preferred_language": "hau_NG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=postbirth.mother.audio.0_12.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 2,
                    "short_name": 'postbirth.mother.audio.0_12.mon_wed.9_11',
                    "default_schedule": 4
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change baby completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.contact, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 2)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_friend_only_change_baby(self):
        # Setup
        # make registration
        self.make_registration_friend_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_baby",
            "data": {},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % change_data[
                "mother_id"],
            json={
                "id": change_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+2345059992222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "linked_to": "629eaf3c-04e5-4404-8a27-3ab3b811326a",
                    "preferred_msg_type": "audio",
                    "preferred_msg_days": "mon_wed",
                    "preferred_msg_times": "9_11",
                    "preferred_language": "hau_NG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=postbirth.mother.audio.0_12.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 2,
                    "short_name": 'postbirth.mother.audio.0_12.mon_wed.9_11',
                    "default_schedule": 4
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock household messageset lookup
        query_string = '?short_name=postbirth.household.text.0_52'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 17,
                    "short_name": 'postbirth.household.text.0_52',
                    "default_schedule": 3
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )
        # mock household schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/3/',
            json={"id": 3, "day_of_week": "5"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change baby completed")
        d_mom = SubscriptionRequest.objects.filter(
            contact=change_data["mother_id"])[0]
        self.assertEqual(d_mom.contact, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d_mom.messageset, 2)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "hau_NG")
        self.assertEqual(d_mom.schedule, 4)

        d_hh = SubscriptionRequest.objects.filter(
            contact="629eaf3c-04e5-4404-8a27-3ab3b811326a")[0]
        self.assertEqual(d_hh.contact, "629eaf3c-04e5-4404-8a27-3ab3b811326a")
        self.assertEqual(d_hh.messageset, 17)
        self.assertEqual(d_hh.next_sequence_number, 1)
        self.assertEqual(d_hh.lang, "hau_NG")
        self.assertEqual(d_hh.schedule, 3)


class TestChangeLanguage(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_only_change_language(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {
                "household_id": None,
                "new_language": "pcm_NG"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"lang": "pcm_NG"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change language completed")
        assert len(responses.calls) == 2

    @responses.activate
    def test_friend_only_change_language(self):
        # Setup
        # make registration
        self.make_registration_friend_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {
                "household_id": "629eaf3c-04e5-4404-8a27-3ab3b811326a",
                "new_language": "pcm_NG"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock mother get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"lang": "pcm_NG"},
            status=200, content_type='application/json',
        )
        # mock household get subscription request
        subscription_id = "ece53dbd-962f-4b9a-8546-759b059a2ae1"
        query_string = '?active=True&id=%s' % change_data["data"][
            "household_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["data"]["household_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"lang": "pcm_NG"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change language completed")
        assert len(responses.calls) == 4


class TestChangeUnsubscribeHousehold(AuthenticatedAPITestCase):

    @responses.activate
    def test_unsubscribe_household(self):
        # Setup
        # make registration
        self.make_registration_friend_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "unsubscribe_household_only",
            "data": {
                "household_id": "629eaf3c-04e5-4404-8a27-3ab3b811326a",
                "loss_reason": "miscarriage"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["data"][
            "household_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["data"]["household_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Unsubscribe household completed")
        assert len(responses.calls) == 2


class TestChangeUnsubscribeMother(AuthenticatedAPITestCase):

    @responses.activate
    def test_unsubscribe_mother(self):
        # Setup
        # make registration
        self.make_registration_friend_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "unsubscribe_mother_only",
            "data": {
                "loss_reason": "miscarriage"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Unsubscribe mother completed")
        assert len(responses.calls) == 2


class TestChangeLoss(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_only_change_loss(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {"loss_reason": "miscarriage"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % change_data[
                "mother_id"],
            json={
                "id": change_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+2345059992222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "linked_to": None,
                    "preferred_msg_type": "audio",
                    "preferred_msg_days": "mon_wed",
                    "preferred_msg_times": "9_11",
                    "preferred_language": "hau_NG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=miscarriage.mother.audio.0_2.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 19,
                    "short_name": 'miscarriage.mother.audio.0_2.mon_wed.9_11',
                    "default_schedule": 4
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change loss completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.contact, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)
