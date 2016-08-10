import json
import responses

from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved

from .models import Record, record_post_save
from .tasks import add_unique_id_to_identity


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()


class AuthenticatedAPITestCase(APITestCase):

    def _replace_post_save_hooks(self):
        def has_listeners():
            return post_save.has_listeners(Record)
        assert has_listeners(), (
            "Record model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=record_post_save,
                             sender=Record)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Record model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks(self):
        def has_listeners():
            return post_save.has_listeners(Record)
        assert not has_listeners(), (
            "Record model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(record_post_save, sender=Record)

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self._replace_post_save_hooks()

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
        self._restore_post_save_hooks()


class TestRecordCreation(AuthenticatedAPITestCase):

    def test_record_create_unique_ten_digit(self):
        # Setup
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "health_id"
        }
        # Execute
        Record.objects.create(**data)
        # Check
        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 10)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")
        self.assertEqual(d.length, 10)
        self.assertEqual(d.write_to, "health_id")

    def test_record_create_unique_ten_digit_two(self):
        # Setup
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "health_id"
        }
        Record.objects.create(**data)
        data2 = {
            "identity": "c304f463-6db4-4f89-a095-46319da06ac9",
            "write_to": "health_id"
        }
        # Execute
        Record.objects.create(**data2)
        # Check
        self.assertEqual(Record.objects.all().count(), 2)


class TestRecordAPI(AuthenticatedAPITestCase):

    def test_webook_api_create_unique_ten_digit(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.created",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "created_at": "2016-04-21T12:12:26.614872+00:00",
                "created_by": "app_ussd",
                "communicate_through": None,
                "updated_by": "mikej",
                "updated_at": "2016-04-21T12:12:26.614960+00:00",
                "details": {
                    "mother_id": "18efafd8-065f-40d4-b4e9-71742836e820",
                    "default_addr_type": "msisdn",
                    "role": "head_of_household",
                    "addresses": {
                        "msisdn": {
                            "+27123": {}
                        }
                    },
                    "preferred_msg_type": "text"
                },
                "operator": None,
                "id": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
                "version": 1
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 10)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")

    def test_webook_api_create_unique_twelve_digit(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.created",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "created_at": "2016-04-21T12:12:26.614872+00:00",
                "created_by": "app_ussd",
                "communicate_through": None,
                "updated_by": "mikej",
                "updated_at": "2016-04-21T12:12:26.614960+00:00",
                "details": {
                    "mother_id": "18efafd8-065f-40d4-b4e9-71742836e820",
                    "default_addr_type": "msisdn",
                    "role": "head_of_household",
                    "addresses": {
                        "msisdn": {
                            "+27123": {}
                        }
                    },
                    "preferred_msg_type": "text",
                    "uniqueid_field_length": 12
                },
                "operator": None,
                "id": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
                "version": 1
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 12)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")

    def test_webook_api_create_unique_named_amazing(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.created",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "created_at": "2016-04-21T12:12:26.614872+00:00",
                "created_by": "app_ussd",
                "communicate_through": None,
                "updated_by": "mikej",
                "updated_at": "2016-04-21T12:12:26.614960+00:00",
                "details": {
                    "mother_id": "18efafd8-065f-40d4-b4e9-71742836e820",
                    "default_addr_type": "msisdn",
                    "role": "head_of_household",
                    "addresses": {
                        "msisdn": {
                            "+27123": {}
                        }
                    },
                    "preferred_msg_type": "text",
                    "uniqueid_field_name": "amazing"
                },
                "operator": None,
                "id": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
                "version": 1
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 10)
        self.assertEqual(d.write_to, "amazing")
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")

    def test_webook_api_missing_identity(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.created",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "created_at": "2016-04-21T12:12:26.614872+00:00",
                "created_by": "app_ussd",
                "communicate_through": None,
                "updated_by": "mikej",
                "updated_at": "2016-04-21T12:12:26.614960+00:00",
                "details": {},
                "operator": None,
                "version": 1
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'id': [
            'This field is required.']})


class TestRecordTasks(AuthenticatedAPITestCase):

    @responses.activate
    def test_identity_patch(self):
        # Setup
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % (
                "70097580-c9fe-4f92-a55e-8f5f54b19799",),
            json={
                "id": "70097580-c9fe-4f92-a55e-8f5f54b19799",
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+256720000222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "preferred_language": "eng_UG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock patch subscription request
        payload = {
            "details": {
                "default_addr_type": "msisdn",
                "addresses": {
                    "msisdn": {
                        "+256720000222": {}
                    }
                },
                "receiver_role": "mother",
                "preferred_language": "eng_UG",
                "unique_id": 1234567890
            }
        }
        responses.add(
            responses.PATCH,
            'http://localhost:8001/api/v1/identities/%s/' % (
                "70097580-c9fe-4f92-a55e-8f5f54b19799",),
            json=payload,
            status=201, content_type='application/json',
        )

        # Execute
        result = add_unique_id_to_identity.apply_async(
            kwargs={
                "identity": "70097580-c9fe-4f92-a55e-8f5f54b19799",
                "unique_id": 1234567890,
                "write_to": "unique_id"
            })

        # Check
        self.assertEqual(
            result.get(),
            "Identity <70097580-c9fe-4f92-a55e-8f5f54b19799> now has "
            "<unique_id> of <1234567890>")

    @responses.activate
    def test_identity_patch_not_found(self):
        # Setup
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % (
                "70097580-c9fe-4f92-a55e-8f5f54b19799",),
            json={
                "error": "object not found",
                },
            status=404, content_type='application/json',
        )

        # Execute
        result = add_unique_id_to_identity.apply_async(
            kwargs={
                "identity": "70097580-c9fe-4f92-a55e-8f5f54b19799",
                "unique_id": 1234567890,
                "write_to": "unique_id"
            })

        # Check
        self.assertEqual(
            result.get(),
            "Identity <70097580-c9fe-4f92-a55e-8f5f54b19799> not found")
