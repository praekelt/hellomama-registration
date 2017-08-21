import datetime
import json
import responses

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved

from hellomama_registration import utils
from registrations.models import (
    Source, Registration, SubscriptionRequest, registration_post_save,
    fire_created_metric, fire_unique_operator_metric, fire_message_type_metric,
    fire_receiver_type_metric, fire_source_metric, fire_language_metric,
    fire_state_metric, fire_role_metric)
from .models import (
    Change, change_post_save, fire_language_change_metric,
    fire_baby_change_metric, fire_loss_change_metric,
    fire_message_change_metric)
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
        post_save.disconnect(receiver=fire_language_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_baby_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_loss_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_message_change_metric,
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
        post_save.connect(receiver=change_post_save,
                          sender=Change)
        post_save.connect(receiver=fire_language_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_baby_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_loss_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_message_change_metric,
                          sender=Change)
        post_save.connect(receiver=model_saved,
                          dispatch_uid='instance-saved-hook')

    def _replace_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
        assert has_listeners(), (
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
        assert not has_listeners(), (
            "Registration model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
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

    def make_source_adminuser(self):
        data = {
            "name": "test_ussd_source_adminuser",
            "authority": "hw_full",
            "user": User.objects.get(username='testadminuser')
        }
        return Source.objects.create(**data)

    def make_source_normaluser(self):
        data = {
            "name": "test_voice_source_normaluser",
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
            "source": self.make_source_normaluser()
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
                "preg_week": "11",
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
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})
        self.assertEqual(d.created_by, self.adminuser)

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
        self.assertEqual(d.source.name, 'test_voice_source_normaluser')
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
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)  # Should ignore True post_data
        self.assertEqual(d.data, {"test_key1": "test_value1"})


class TestChangeListAPI(AuthenticatedAPITestCase):

    def test_list_changes(self):
        # Setup
        change1 = self.make_change_adminuser()
        change2 = self.make_change_normaluser()
        change3 = self.make_change_normaluser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/changes/',
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["id"], str(change3.id))
        self.assertEqual(body["results"][1]["id"], str(change2.id))
        self.assertIsNone(body["previous"])
        self.assertIsNotNone(body["next"])

        # Check pagination
        body = self.adminclient.get(body["next"]).json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["id"], str(change1.id))
        self.assertIsNotNone(body["previous"])
        self.assertIsNone(body["next"])

        body = self.adminclient.get(body["previous"]).json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["id"], str(change3.id))
        self.assertEqual(body["results"][1]["id"], str(change2.id))
        self.assertIsNone(body["previous"])
        self.assertIsNotNone(body["next"])

    def test_list_changes_filtered(self):
        # Setup
        self.make_change_adminuser()
        change2 = self.make_change_normaluser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/changes/?source=%s' % change2.source.id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(change2.id))


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
    def test_prebirth_text_to_audio_week28_new_short_name(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "new_short_name": "prebirth.mother.audio.10_42.tue_thu.9_11",
                "new_language": "ibo_NG"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 54,
                    "messageset": 1,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/1/',
            json={
                "id": 1,
                "short_name": 'prebirth.mother.text.10_42',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock messageset via shortname lookup
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
        # mock schedule 6 lookup
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 4)
        self.assertEqual(d.next_sequence_number, 36)  # week 28 - 18*2
        self.assertEqual(d.lang, "ibo_NG")
        self.assertEqual(d.schedule, 6)

    @responses.activate
    def test_prebirth_text_to_text_new_short_name(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "new_short_name": "prebirth.mother.text.0_9",
                "new_language": "ibo_NG"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 10,
                    "messageset": 1,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/1/',
            json={
                "id": 1,
                "short_name": 'prebirth.mother.text.10_42',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock messageset via shortname lookup
        query_string = '?short_name=prebirth.mother.text.0_9'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 4,
                    "short_name": 'prebirth.mother.text.0_9',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 4)
        self.assertEqual(d.next_sequence_number, 10)
        self.assertEqual(d.lang, "ibo_NG")
        self.assertEqual(d.schedule, 1)

    @responses.activate
    def test_prebirth_text_to_audio_week28(self):
        # Setup
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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 54,
                    "messageset": 1,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/1/',
            json={
                "id": 1,
                "short_name": 'prebirth.mother.text.10_42',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock messageset via shortname lookup
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
        # mock schedule 6 lookup
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 4)
        self.assertEqual(d.next_sequence_number, 36)  # week 28 - 18*2
        self.assertEqual(d.lang, "eng_NG")
        self.assertEqual(d.schedule, 6)

    @responses.activate
    def test_postbirth_text_to_audio_week12(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "mon_wed",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 36,
                    "messageset": 7,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/7/',
            json={
                "id": 7,
                "short_name": 'postbirth.mother.text.0_12',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=postbirth.mother.audio.0_12.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 9,
                    "short_name": 'postbirth.mother.audio.0_12.mon_wed.9_11',
                    "default_schedule": 4
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 9)
        self.assertEqual(d.next_sequence_number, 24)  # week 12 - 12*2
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_postbirth_text_to_audio_week13(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "mon_wed",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 2,
                    "messageset": 8,
                    "schedule": 2
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/8/',
            json={
                "id": 8,
                "short_name": 'postbirth.mother.text.13_52',
                "default_schedule": 2
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 2 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/2/',
            json={"id": 2, "day_of_week": "2,4"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=postbirth.mother.audio.13_52.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 13,
                    "short_name": 'postbirth.mother.audio.13_52.mon_wed.9_11',
                    "default_schedule": 8
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 8 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/8/',
            json={"id": 8, "day_of_week": "3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 13)
        self.assertEqual(d.next_sequence_number, 1)  # week 13 - 1*1
        self.assertEqual(d.schedule, 8)

    @responses.activate
    def test_postbirth_text_to_audio_week14(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "mon_wed",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 4,
                    "messageset": 8,
                    "schedule": 2
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/8/',
            json={
                "id": 8,
                "short_name": 'postbirth.mother.text.13_52',
                "default_schedule": 2
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 2 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/2/',
            json={"id": 2, "day_of_week": "2,4"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=postbirth.mother.audio.13_52.mon_wed.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 13,
                    "short_name": 'postbirth.mother.audio.13_52.mon_wed.9_11',
                    "default_schedule": 8
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 8 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/8/',
            json={"id": 8, "day_of_week": "3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 13)
        self.assertEqual(d.next_sequence_number, 2)  # week 14 - 2*1
        self.assertEqual(d.schedule, 8)

    @responses.activate
    def test_miscarriage_text_to_audio_week1(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "mon_wed",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get current subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 1,
                    "messageset": 18,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/18/',
            json={
                "id": 18,
                "short_name": 'miscarriage.mother.text.0_2',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
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
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_miscarriage_text_to_audio_week2(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "audio",
                "voice_days": "mon_wed",
                "voice_times": "9_11"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get current subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 3,
                    "messageset": 18,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/18/',
            json={
                "id": 18,
                "short_name": 'miscarriage.mother.text.0_2',
                "default_schedule": 1
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
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
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 2)
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_prebirth_audio_to_text_week28(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "text",
                "voice_days": None,
                "voice_times": None
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 36,
                    "messageset": 2,
                    "schedule": 4
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/2/',
            json={
                "id": 2,
                "short_name": 'prebirth.mother.audio.10_42.mon_wed.9_11',
                "default_schedule": 4
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=prebirth.mother.text.10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 1,
                    "short_name": 'prebirth.mother.text.10_42',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 1)
        self.assertEqual(d.next_sequence_number, 54)  # week 28 - 18*3
        self.assertEqual(d.schedule, 1)

    @responses.activate
    def test_postbirth_audio_to_text_week12(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "text",
                "voice_days": None,
                "voice_times": None
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 24,
                    "messageset": 9,
                    "schedule": 4
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/9/',
            json={
                "id": 9,
                "short_name": 'postbirth.mother.audio.0_12.mon_wed.9_11',
                "default_schedule": 4
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=postbirth.mother.text.0_12'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 7,
                    "short_name": 'postbirth.mother.text.0_12',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 7)
        self.assertEqual(d.next_sequence_number, 36)  # week 12 - 12*3
        self.assertEqual(d.schedule, 1)

    @responses.activate
    def test_postbirth_audio_to_text_week13(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "text",
                "voice_days": None,
                "voice_times": None
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 1,
                    "messageset": 13,
                    "schedule": 8
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/13/',
            json={
                "id": 13,
                "short_name": 'postbirth.mother.audio.13_52.mon_wed.9_11',
                "default_schedule": 8
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 8 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/8/',
            json={"id": 8, "day_of_week": "3"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=postbirth.mother.text.13_52'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 8,
                    "short_name": 'postbirth.mother.text.13_52',
                    "default_schedule": 2
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 2 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/2/',
            json={"id": 2, "day_of_week": "2,4"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 8)
        self.assertEqual(d.next_sequence_number, 2)  # week 13 - 1*2
        self.assertEqual(d.schedule, 2)

    @responses.activate
    def test_miscarriage_audio_to_text_week2(self):
        # Setup
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {
                "msg_type": "text",
                "voice_days": None,
                "voice_times": None
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get current subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "lang": "eng_NG",
                    "next_sequence_number": 4,
                    "messageset": 19,
                    "schedule": 4
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock current messageset lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/19/',
            json={
                "id": 19,
                "short_name": 'miscarriage.mother.audio.0_2.mon_wed.9_11',
                "default_schedule": 4
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 4 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/4/',
            json={"id": 4, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock new messageset via shortname lookup
        query_string = '?short_name=miscarriage.mother.text.0_2'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 18,
                    "short_name": 'miscarriage.mother.text.0_2',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule 1 lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3,5"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change messaging completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.messageset, 18)
        self.assertEqual(d.next_sequence_number, 6)
        self.assertEqual(d.schedule, 1)


class TestChangeBaby(AuthenticatedAPITestCase):

    @responses.activate
    def test_change_baby_multiple_registrations(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 2)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)

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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        # mock mother identity lookup
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
        query_string = '?short_name=postbirth.household.audio.0_52.fri.9_11'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 17,
                    "short_name": 'postbirth.household.audio.0_52.fri.9_11',
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
            identity=change_data["mother_id"])[0]
        self.assertEqual(d_mom.identity,
                         "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d_mom.messageset, 2)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "hau_NG")
        self.assertEqual(d_mom.schedule, 4)

        d_hh = SubscriptionRequest.objects.filter(
            identity="629eaf3c-04e5-4404-8a27-3ab3b811326a")[0]
        self.assertEqual(d_hh.identity, "629eaf3c-04e5-4404-8a27-3ab3b811326a")
        self.assertEqual(d_hh.messageset, 17)
        self.assertEqual(d_hh.next_sequence_number, 1)
        self.assertEqual(d_hh.lang, "hau_NG")
        self.assertEqual(d_hh.schedule, 3)

    @responses.activate
    def test_mother_only_change_baby_text(self):
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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "preferred_msg_type": "text",
                    "preferred_language": "hau_NG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=postbirth.mother.text.0_12'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 7,
                    "short_name": 'postbirth.mother.text.0_12',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change baby completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 7)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 1)


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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        query_string = '?active=True&identity=%s' % change_data["data"][
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
                "reason": "miscarriage"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["data"][
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
                "reason": "miscarriage"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
    def test_change_loss_multiple_registrations(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {"reason": "miscarriage"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_mother_only_change_loss(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {"reason": "miscarriage"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_friend_only_change_loss(self):
        # Setup
        # make registration
        self.make_registration_friend_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {"reason": "miscarriage"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock mother get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock mother identity lookup
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
        # mock friend get subscription request
        subscription_id = "ece53dbd-962f-4b9a-8546-759b059a2ae1"
        query_string = '?active=True&identity=%s' % (
            "629eaf3c-04e5-4404-8a27-3ab3b811326a")
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": "629eaf3c-04e5-4404-8a27-3ab3b811326a",
                    "active": True,
                    "lang": "eng_NG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock household patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change loss completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 19)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 4)

    @responses.activate
    def test_mother_only_change_loss_text(self):
        # Setup
        # make registration
        self.make_registration_mother_only()
        # make change object
        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {"reason": "miscarriage"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "07f4d95c-ad78-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&identity=%s' % change_data["mother_id"]
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
                    "preferred_msg_type": "text",
                    "preferred_language": "hau_NG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=miscarriage.mother.text.0_2'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 18,
                    "short_name": 'miscarriage.mother.text.0_2',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "0,2"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change loss completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(d.messageset, 18)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "hau_NG")
        self.assertEqual(d.schedule, 1)


class TestMetrics(AuthenticatedAPITestCase):

    @responses.activate
    def test_language_change_metric(self):
        """
        When a new change is created, a sum metric should be fired if it is a
        language change
        """
        # deactivate Testsession for this test
        self.session = None
        # add metric post response
        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')
        post_save.connect(fire_language_change_metric, sender=Change)

        self.make_change_normaluser()

        [last_call1, last_call2] = responses.calls
        self.assertEqual(json.loads(last_call1.request.body), {
            "registrations.change.language.sum": 1.0
        })

        self.assertEqual(json.loads(last_call2.request.body), {
            "registrations.change.language.total.last": 1.0
        })

        post_save.disconnect(fire_language_change_metric, sender=Change)

    @responses.activate
    def test_baby_change_metric(self):
        """
        When a new change is created, a sum metric should be fired if it is a
        pregnancy to baby change
        """
        # deactivate Testsession for this test
        self.session = None
        # add metric post response
        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')
        post_save.connect(fire_baby_change_metric, sender=Change)

        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_baby",
            "data": {},
            "source": self.make_source_adminuser()
        }
        Change.objects.create(**change_data)

        [last_call1, last_call2] = responses.calls
        self.assertEqual(json.loads(last_call1.request.body), {
            "registrations.change.pregnant_to_baby.sum": 1.0
        })

        self.assertEqual(json.loads(last_call2.request.body), {
            "registrations.change.pregnant_to_baby.total.last": 1.0
        })

        post_save.disconnect(fire_baby_change_metric, sender=Change)

    @responses.activate
    def test_loss_change_metric(self):
        """
        When a new change is created, a sum metric should be fired if it is a
        pregnancy to loss change
        """
        # deactivate Testsession for this test
        self.session = None
        # add metric post response
        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')
        post_save.connect(fire_loss_change_metric, sender=Change)

        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_loss",
            "data": {},
            "source": self.make_source_adminuser()
        }
        Change.objects.create(**change_data)

        [last_call1, last_call2] = responses.calls
        self.assertEqual(json.loads(last_call1.request.body), {
            "registrations.change.pregnant_to_loss.sum": 1.0
        })

        self.assertEqual(json.loads(last_call2.request.body), {
            "registrations.change.pregnant_to_loss.total.last": 1.0
        })

        post_save.disconnect(fire_loss_change_metric, sender=Change)

    @responses.activate
    def test_message_change_metric(self):
        """
        When a new change is created, a sum metric should be fired if it is a
        messaging change
        """
        # deactivate Testsession for this test
        self.session = None
        # add metric post response
        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')
        post_save.connect(fire_message_change_metric, sender=Change)

        change_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_messaging",
            "data": {},
            "source": self.make_source_adminuser()
        }
        Change.objects.create(**change_data)

        [last_call1, last_call2] = responses.calls
        self.assertEqual(json.loads(last_call1.request.body), {
            "registrations.change.messaging.sum": 1.0
        })

        self.assertEqual(json.loads(last_call2.request.body), {
            "registrations.change.messaging.total.last": 1.0
        })

        post_save.disconnect(fire_message_change_metric, sender=Change)


class IdentityStoreOptoutViewTest(AuthenticatedAPITestCase):
    """
    Tests related to the optout identity store view.
    """
    url = '/optout/'

    def setUp(self):
        self.factory = RequestFactory()
        super(IdentityStoreOptoutViewTest, self).setUp()

    def optout_search_callback(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [{
                'identity': "846877e6-afaa-43de-acb1-09f61ad4de99",
                'details': {
                    'name': "testing",
                    'addresses': {
                        'msisdn': {
                            '+1234': {}
                        },
                    },
                    'language': "eng_NG",
                },
                'optout_type': "forget",
                'optout_reason': "miscarriage",
                'optout_source': "ussd_public",
            }, {
                'identity': "846877e6-afaa-43de-1111-09f61ad4de99",
                'details': {
                    'name': "testing",
                    'addresses': {
                        'msisdn': {
                            '+1234': {}
                        },
                    },
                    'language': "eng_NG",
                },
                'optout_type': "forget",
                'optout_reason': "miscarriage",
                'optout_source': "ussd_public",
            }]
        }
        return (200, headers, json.dumps(resp))

    def optout_search_callback_other(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{
                'identity': "629eaf3c-04e5-1111-8a27-3ab3b811326a",
                'details': {
                    'name': "testing",
                    'addresses': {
                        'msisdn': {
                            '+1234': {}
                        },
                    },
                    'language': "eng_NG",
                },
                'optout_type': "forget",
                'optout_reason': "other",
                'optout_source': "ivr_public",
            }]
        }
        return (200, headers, json.dumps(resp))

    @responses.activate
    def test_identity_optout_valid(self):

        self.make_registration_mother_only()
        registration = self.make_registration_mother_only()
        registration.mother_id = '846877e6-afaa-43de-1111-09f61ad4de99'
        registration.save()

        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')

        url = 'http://localhost:8001/api/v1/optouts/search/?' \
              'reason=miscarriage'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback,
            match_querystring=True, content_type="application/json")

        url = 'http://localhost:8001/api/v1/optouts/search/'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback,
            match_querystring=True, content_type="application/json")

        url = 'http://localhost:8001/api/v1/optouts/search/?' \
              'request_source=ussd_public'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback,
            match_querystring=True, content_type="application/json")

        request = {
            'identity': "846877e6-afaa-43de-acb1-09f61ad4de99",
            'details': {
                'name': "testing",
                'addresses': {
                    'msisdn': {
                        '+1234': {}
                    },
                },
                'language': "eng_NG",
            },
            'optout_type': "forget",
            'optout_reason': "miscarriage",
            'optout_source': "ussd_public",
        }
        response = self.adminclient.post('/api/v1/optout/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(responses.calls), 12)

        self.assertEqual(json.loads(responses.calls[0].request.body), {
            "optout.receiver_type.mother_only.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[2].request.body), {
            "optout.receiver_type.mother_only.total.last": 2.0
        })
        self.assertEqual(json.loads(responses.calls[3].request.body), {
            "optout.reason.miscarriage.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[5].request.body), {
            "optout.reason.miscarriage.total.last": 2.0
        })
        self.assertEqual(json.loads(responses.calls[6].request.body), {
            "optout.msg_type.text.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[8].request.body), {
            "optout.msg_type.text.total.last": 2.0
        })
        self.assertEqual(json.loads(responses.calls[9].request.body), {
            "optout.source.ussd.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[11].request.body), {
            "optout.source.ussd.total.last": 2.0
        })

    @responses.activate
    def test_identity_optout_friend_only(self):

        friend_registration = self.make_registration_friend_only()
        friend_registration.data['receiver_id'] = '629eaf3c-04e5-1111-8a27-3ab3b811326a'  # noqa
        friend_registration.data['msg_type'] = 'audio'
        friend_registration.mother_id = '846877e6-afaa-1111-1111-09f61ad4de99'
        friend_registration.save()

        responses.add(responses.POST,
                      "http://metrics-url/metrics/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')

        url = 'http://localhost:8001/api/v1/optouts/search/?' \
              'reason=other'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback_other,
            match_querystring=True, content_type="application/json")

        url = 'http://localhost:8001/api/v1/optouts/search/'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback_other,
            match_querystring=True, content_type="application/json")

        url = 'http://localhost:8001/api/v1/optouts/search/?' \
              'request_source=ivr_public'
        responses.add_callback(
            responses.GET, url, callback=self.optout_search_callback_other,
            match_querystring=True, content_type="application/json")

        request = {
            'identity': "629eaf3c-04e5-1111-8a27-3ab3b811326a",
            'details': {
                'name': "testing",
                'addresses': {
                    'msisdn': {
                        '+1234': {}
                    },
                },
                'language': "eng_NG",
            },
            'optout_type': "forget",
            'optout_reason': "other",
            'optout_source': "ivr_public",
        }
        response = self.adminclient.post('/api/v1/optout/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(responses.calls), 12)

        self.assertEqual(json.loads(responses.calls[0].request.body), {
            "optout.receiver_type.friend_only.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[2].request.body), {
            "optout.receiver_type.friend_only.total.last": 1.0
        })
        self.assertEqual(json.loads(responses.calls[3].request.body), {
            "optout.reason.other.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[5].request.body), {
            "optout.reason.other.total.last": 1.0
        })
        self.assertEqual(json.loads(responses.calls[6].request.body), {
            "optout.msg_type.audio.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[8].request.body), {
            "optout.msg_type.audio.total.last": 1.0
        })
        self.assertEqual(json.loads(responses.calls[9].request.body), {
            "optout.source.ivr.sum": 1.0
        })
        self.assertEqual(json.loads(responses.calls[11].request.body), {
            "optout.source.ivr.total.last": 1.0
        })

    @responses.activate
    def test_identity_optout_invalid(self):

        self.make_registration_mother_only()

        request = {
            'details': {
                'name': "testing",
                'addresses': {
                    'msisdn': {
                        '+1234': {}
                    },
                },
                'language': "eng_NG",
            },
            'optout_type': "forget",
            'optout_reason': "miscarriage",
        }
        response = self.adminclient.post('/api/v1/optout/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(utils.json_decode(response.content),
                         {'reason':
                          '"identity", "optout_reason" and "optout_source" '
                          'must be specified.'})
        self.assertEqual(len(responses.calls), 0)


class AdminViewsTest(AuthenticatedAPITestCase):

    """
    Tests related to the optout control interface view.
    """

    def add_messageset_language_callback(self):
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset_languages/',
            json={
                "2": ["afr_ZA", "eng_ZA"],
                "4": ["afr_ZA", "eng_ZA", "zul_ZA"]
            },
            status=200,
            content_type='application/json')

    def add_messageset_via_short_name(self, short_name, id=13, schedule=8):
        query_string = '?short_name=%s' % short_name
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": id,
                    "short_name": short_name,
                    "default_schedule": schedule
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

    def test_ci_optout_invalid(self):
        request = {}

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/optout_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(utils.json_decode(response.content),
                         {"mother_id": ["This field is required."]})
        self.assertEqual(len(responses.calls), 0)

    def test_ci_optout(self):
        request = {
            "mother_id": "mother-id-123"
        }

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/optout_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 201)
        change = Change.objects.last()
        self.assertEqual(change.mother_id, "mother-id-123")
        self.assertEqual(change.action, "unsubscribe_mother_only")
        self.assertEqual(change.source.name, "test_ussd_source_adminuser")

    def test_ci_optout_no_source_username(self):
        request = {
            "mother_id": "mother-id-123"
        }

        user = User.objects.get(username="testnormaluser")

        response = self.normalclient.post('/api/v1/optout_admin/',
                                          json.dumps(request),
                                          content_type='application/json')

        self.assertEqual(response.status_code, 201)
        change = Change.objects.last()
        self.assertEqual(change.mother_id, "mother-id-123")
        self.assertEqual(change.action, "unsubscribe_mother_only")

        source = Source.objects.last()
        self.assertEqual(source.name, user.username)
        self.assertEqual(source.user, user)
        self.assertEqual(source.authority, "advisor")

    def test_ci_optout_no_source(self):
        request = {
            "mother_id": "mother-id-123"
        }

        user = User.objects.get(username="testnormaluser")
        user.first_name = "John"
        user.last_name = "Doe"
        user.save()

        response = self.normalclient.post('/api/v1/optout_admin/',
                                          json.dumps(request),
                                          content_type='application/json')

        self.assertEqual(response.status_code, 201)
        change = Change.objects.last()
        self.assertEqual(change.mother_id, "mother-id-123")
        self.assertEqual(change.action, "unsubscribe_mother_only")

        source = Source.objects.last()
        self.assertEqual(source.name, user.get_full_name())
        self.assertEqual(source.user, user)
        self.assertEqual(source.authority, "advisor")

    def test_ci_change_no_identity(self):
        request = {}

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(utils.json_decode(response.content),
                         {"mother_id": ["This field is required."]})
        self.assertEqual(len(responses.calls), 0)

    def test_ci_change_invalid(self):
        request = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99"
        }

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            utils.json_decode(response.content),
            {"non_field_errors": ["One of these fields must be populated: messageset, language"]})  # noqa

    @responses.activate
    def test_ci_change_language(self):
        request = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "language": "eng_ZA"
        }

        self.add_messageset_language_callback()

        # mock get subscription request
        subscription_id = "846877e6-afaa-43de-acb1-09f61ad4de99"
        query_string = '?active=True&identity=%s' % request["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": request["mother_id"],
                    "active": True,
                    "lang": "eng_NG",
                    "next_sequence_number": 36,
                    "messageset": 2,
                    "schedule": 1
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 201)
        change = Change.objects.last()
        self.assertEqual(change.mother_id,
                         "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(change.action, "change_language")
        self.assertEqual(change.data, {"new_language": "eng_ZA"})

    def test_ci_change_messaging(self):
        request = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "messageset": "messageset_one"
        }

        self.make_source_adminuser()
        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 201)
        change = Change.objects.last()
        self.assertEqual(change.mother_id,
                         "846877e6-afaa-43de-acb1-09f61ad4de99")
        self.assertEqual(change.action, "change_messaging")
        self.assertEqual(change.data, {"new_short_name": "messageset_one"})

    @responses.activate
    def test_ci_change_language_and_messaging(self):
        identity = "846877e6-afaa-43de-acb1-09f61ad4de99"
        request = {
            "mother_id": identity,
            "messageset": "messageset_one",
            "language": "eng_ZA"
        }

        self.make_source_adminuser()

        self.add_messageset_language_callback()

        self.add_messageset_via_short_name("messageset_one", 2)

        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 201)

        changes = Change.objects.filter(mother_id=identity)
        self.assertEqual(changes.count(), 1)

        self.assertEqual(changes[0].action, "change_messaging")
        self.assertEqual(changes[0].data, {
            "new_short_name": "messageset_one",
            "new_language": "eng_ZA"
        })

    @responses.activate
    def test_ci_change_language_and_messaging_invalid(self):
        identity = "846877e6-afaa-43de-acb1-09f61ad4de99"
        request = {
            "mother_id": identity,
            "messageset": "messageset_one",
            "language": "zul_ZA"
        }

        self.make_source_adminuser()

        self.add_messageset_language_callback()

        self.add_messageset_via_short_name("messageset_one", 2)

        response = self.adminclient.post('/api/v1/change_admin/',
                                         json.dumps(request),
                                         content_type='application/json')

        self.assertEqual(response.status_code, 400)


class AddChangeViewsTest(AuthenticatedAPITestCase):
    """
    Tests related to the adding of changes view.
    """
    def mock_identity_lookup(self, msisdn, identity_id):
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/search/?details__addresses__msisdn=%s' % msisdn,  # noqa
            json={
                "count": 1, "next": None, "previous": None,
                "results": [{
                    "id": identity_id,
                    "details": {}
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

    def mock_identity_optout(self):
        responses.add(responses.POST,
                      "http://localhost:8001/api/v1/optout/",
                      json={"foo": "bar"},
                      status=200, content_type='application/json')

    @responses.activate
    def test_add_change_language(self):
        # Setup
        self.make_source_adminuser()
        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"

        self.mock_identity_lookup("%2B2347031221927", mother_id)
        post_data = {
            "msisdn": "07031221927",
            "action": "change_language",
            "data": {"new_language": "english"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"new_language": "eng_NG"})
        self.assertEqual(d.created_by, self.adminuser)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_add_change_messaging(self):
        # Setup
        self.make_source_adminuser()
        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"

        self.mock_identity_lookup("%2B2347031221927", mother_id)
        post_data = {
            "msisdn": "07031221927",
            "action": "change_messaging",
            "data":  {
                "voice_days": "tuesday_and_thursday",
                "voice_times": "2-5pm",
                "msg_type": "voice"
            }

        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'change_messaging')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {
            "voice_days": "tue_thu",
            "voice_times": "2_5",
            "msg_type": "audio"
        })
        self.assertEqual(d.created_by, self.adminuser)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_add_change_unsubscribe(self):
        # Setup
        self.make_source_adminuser()
        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"

        self.mock_identity_lookup("%2B2347031221927", mother_id)
        self.mock_identity_optout()

        post_data = {
            "msisdn": "07031221927",
            "action": "unsubscribe_mother_only",
            "data": {"reason": "miscarriage"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')

        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'unsubscribe_mother_only')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"reason": "miscarriage"})
        self.assertEqual(d.created_by, self.adminuser)

        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_add_change_unsubscribe_household(self):
        # Setup
        self.make_source_adminuser()
        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"
        household_id = "4038a518-2940-4b15-9c5c-9ix9cvx09cv8"

        self.mock_identity_lookup("%2B2347031221927", mother_id)
        self.mock_identity_lookup("%2B2347031221928", household_id)
        self.mock_identity_optout()

        post_data = {
            "msisdn": "07031221927",
            "action": "unsubscribe_household_only",
            "data": {
                "reason": "not_useful",
                "household_msisdn": "07031221928"
            }
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')

        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_ussd_source_adminuser')
        self.assertEqual(d.action, 'unsubscribe_household_only')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data["reason"], "not_useful")
        self.assertEqual(d.data["household_id"], household_id)
        self.assertEqual(d.created_by, self.adminuser)

        self.assertEqual(len(responses.calls), 3)

    @responses.activate
    def test_add_change_missing_field(self):
        # Setup
        post_data = {
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            utils.json_decode(response.content),
            {"msisdn": ["This field is required."]})

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_add_change_no_source(self):
        # Setup
        mother_id = "4038a518-2940-4b15-9c5c-2b7b123b8735"

        self.mock_identity_lookup("%2B2347031221927", mother_id)
        post_data = {
            "msisdn": "07031221927",
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            utils.json_decode(response.content),
            "Source not found for user.")
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_add_change_invalid_field(self):
        # Setup
        post_data = {
            "msisdn": "07031221927",
            "action": "change_everything",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/addchange/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            utils.json_decode(response.content),
            {'action': ['"change_everything" is not a valid choice.']})

        self.assertEqual(len(responses.calls), 0)
