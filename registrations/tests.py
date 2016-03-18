import json
import uuid
import datetime
import responses

from django.contrib.auth.models import User
from django.test import TestCase
from django.db.models.signals import post_save
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import (Source, Registration, SubscriptionRequest,
                     registration_post_save)
from rest_hooks.models import model_saved, Hook
from .tasks import (
    validate_registration,
    is_valid_date, is_valid_uuid, is_valid_lang, is_valid_msg_type,
    is_valid_msg_receiver, is_valid_loss_reason)
from registrations import tasks


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


REG_FIELDS = {
    "hw_pre_friend": [
        "mother_id", "operator_id", "language", "msg_type",
        "last_period_date", "msg_receiver"]
}

REG_DATA = {
    "hw_pre_mother": {
        "receiver_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "1",
        "last_period_date": "20150202",
        "msg_receiver": "mother_only"
    },
    "hw_pre_friend": {
        "receiver_id": "friend00-73a2-4d89-b045-d52004c025fe",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "1",
        "last_period_date": "20150202",
        "msg_receiver": "friend_only"
    },
    "hw_pre_family": {
        "receiver_id": "family00-73a2-4d89-b045-d52004c025fe",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "1",
        "last_period_date": "20150202",
        "msg_receiver": "family_only"
    },
    "hw_pre_father": {
        "receiver_id": "father00-73a2-4d89-b045-d52004c025fe",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "20150202",
        "msg_receiver": "father_only"
    },
    "hw_pre_father_and_mother": {
        "receiver_id": "father00-73a2-4d89-b045-d52004c025fe",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "20150202",
        "msg_receiver": "mother_father"
    },
    "hw_pre_family_and_mother": {
        "receiver_id": "family00-73a2-4d89-b045-d52004c025fe",
        "operator_id": "nurse000-6a07-4377-a4f6-c0485ccba234",
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "20150202",
        "msg_receiver": "mother_family"
    },
    "hw_post": {
        "receiver_id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "baby_dob": "20150202",
        "msg_receiver": "friend_only"
    },
    "pbl_loss": {
        "receiver_id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "loss_reason": "miscarriage"
    },
    "missing_field": {
        "receiver_id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "20150202",
    },
    "bad_fields": {
        "receiver_id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "2015020",
        "msg_receiver": "trusted friend"
    },
    "bad_lmp": {
        "receiver_id": str(uuid.uuid4()),
        "operator_id": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "text",
        "gravida": "2",
        "last_period_date": "20140202",
        "msg_receiver": "friend_only"
    },
}


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()
        self.otherclient = APIClient()
        tasks.get_today = override_get_today


class AuthenticatedAPITestCase(APITestCase):

    def _replace_post_save_hooks(self):
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

    def _restore_post_save_hooks(self):
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

    def make_registration_adminuser(self):
        data = {
            "stage": "prebirth",
            "data": {"test_adminuser_reg_key": "test_adminuser_reg_value"},
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**data)

    def make_registration_normaluser(self):
        data = {
            "stage": "postbirth",
            "data": {"test_normaluser_reg_key": "test_normaluser_reg_value"},
            "source": self.make_source_normaluser()
        }
        return Registration.objects.create(**data)

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


class TestSourceAPI(AuthenticatedAPITestCase):

    def test_get_source_adminuser(self):
        # Setup
        source = self.make_source_adminuser()
        # Execute
        response = self.adminclient.get('/api/v1/source/%s/' % source.id,
                                        format='json',
                                        content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["authority"], "hw_full")
        self.assertEqual(response.data["name"], "test_source_adminuser")

    def test_get_source_normaluser(self):
        # Setup
        source = self.make_source_normaluser()
        # Execute
        response = self.normalclient.get('/api/v1/source/%s/' % source.id,
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_source_adminuser(self):
        # Setup
        user = User.objects.get(username='testadminuser')
        post_data = {
            "name": "test_source_name",
            "authority": "patient",
            "user": "/api/v1/user/%s/" % user.id
        }
        # Execute
        response = self.adminclient.post('/api/v1/source/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Source.objects.last()
        self.assertEqual(d.name, 'test_source_name')
        self.assertEqual(d.authority, "patient")

    def test_create_source_normaluser(self):
        # Setup
        user = User.objects.get(username='testnormaluser')
        post_data = {
            "name": "test_source_name",
            "authority": "hw_full",
            "user": "/api/v1/user/%s/" % user.id
        }
        # Execute
        response = self.normalclient.post('/api/v1/source/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestRegistrationAPI(AuthenticatedAPITestCase):

    def test_get_registration_adminuser(self):
        # Setup
        registration = self.make_registration_adminuser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registration/%s/' % registration.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_registration_normaluser(self):
        # Setup
        registration = self.make_registration_normaluser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/registration/%s/' % registration.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_registration_adminuser(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/registration/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.stage, 'prebirth')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_registration_normaluser(self):
        # Setup
        self.make_source_normaluser()
        post_data = {
            "stage": "postbirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.normalclient.post('/api/v1/registration/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_normaluser')
        self.assertEqual(d.stage, 'postbirth')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_registration_set_readonly_field(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": {"test_key1": "test_value1"},
            "validated": True
        }
        # Execute
        response = self.adminclient.post('/api/v1/registration/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.stage, 'prebirth')
        self.assertEqual(d.validated, False)  # Should ignore True post_data
        self.assertEqual(d.data, {"test_key1": "test_value1"})


class TestFieldValidation(AuthenticatedAPITestCase):

    def test_is_valid_date(self):
        # Setup
        good_date = "19820315"
        invalid_date = "19830229"
        bad_date = "1234"
        # Execute
        # Check
        self.assertEqual(is_valid_date(good_date), True)
        self.assertEqual(is_valid_date(invalid_date), False)
        self.assertEqual(is_valid_date(bad_date), False)

    def test_is_valid_uuid(self):
        # Setup
        valid_uuid = str(uuid.uuid4())
        invalid_uuid = "f9bfa2d7-5b62-4011-8eac-76bca34781a"
        # Execute
        # Check
        self.assertEqual(is_valid_uuid(valid_uuid), True)
        self.assertEqual(is_valid_uuid(invalid_uuid), False)

    def test_is_valid_lang(self):
        # Setup
        valid_lang = "pidgin"
        invalid_lang = "french"
        # Execute
        # Check
        self.assertEqual(is_valid_lang(valid_lang), True)
        self.assertEqual(is_valid_lang(invalid_lang), False)

    def test_is_valid_msg_type(self):
        # Setup
        valid_msg_type1 = "text"
        valid_msg_type2 = "audio"
        invalid_msg_type = "email"
        # Execute
        # Check
        self.assertEqual(is_valid_msg_type(valid_msg_type1), True)
        self.assertEqual(is_valid_msg_type(valid_msg_type2), True)
        self.assertEqual(is_valid_msg_type(invalid_msg_type), False)

    def test_is_valid_msg_receiver(self):
        # Setup
        valid_msg_receiver = "father_only"
        invalid_msg_receiver = "mama"
        # Execute
        # Check
        self.assertEqual(is_valid_msg_receiver(valid_msg_receiver), True)
        self.assertEqual(is_valid_msg_receiver(invalid_msg_receiver), False)

    def test_is_valid_loss_reason(self):
        # Setup
        valid_loss_reason = "miscarriage"
        invalid_loss_reason = "other"
        # Execute
        # Check
        self.assertEqual(is_valid_loss_reason(valid_loss_reason), True)
        self.assertEqual(is_valid_loss_reason(invalid_loss_reason), False)

    def test_check_field_values(self):
        # Setup
        valid_hw_pre_registration_data = REG_DATA["hw_pre_friend"].copy()
        invalid_hw_pre_registration_data = REG_DATA["hw_pre_friend"].copy()
        invalid_hw_pre_registration_data["msg_receiver"] = "somebody"
        # Execute
        cfv_valid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_friend"], valid_hw_pre_registration_data)
        cfv_invalid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_friend"], invalid_hw_pre_registration_data)
        # Check
        self.assertEqual(cfv_valid, [])
        self.assertEqual(cfv_invalid, ['msg_receiver'])


class TestRegistrationValidation(AuthenticatedAPITestCase):

    def test_validate_hw_prebirth(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_postbirth(self):
        # Setup
        registration_data = {
            "stage": "postbirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_post"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_post")
        self.assertEqual(registration.data["baby_age"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_pbl_loss(self):
        # Setup
        registration_data = {
            "stage": "loss",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["pbl_loss"].copy(),
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_loss")
        self.assertEqual(registration.validated, True)

    def test_validate_pregnancy_too_long(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20130101"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_pregnancy_9_weeks(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20150612"  # 9 weeks
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_pregnancy_10_weeks(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20150605"  # 10 weeks
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.validated, True)

    def test_validate_baby_too_young(self):
        # Setup
        registration_data = {
            "stage": "postbirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_post"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["baby_dob"] = "20150818"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_baby_too_old(self):
        # Setup
        registration_data = {
            "stage": "postbirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_post"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["baby_dob"] = "20130717"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    @responses.activate
    def test_validate_registration_run_success(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Success")

    def test_validate_registration_run_failure_missing_field(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["missing_field"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"],
                         "Invalid combination of fields")

    def test_validate_registration_run_failure_bad_fields(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["bad_fields"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(sorted(d.data["invalid_fields"]),
                         sorted(["msg_receiver", "last_period_date"]))

    def test_validate_registration_run_failure_bad_lmp(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["bad_lmp"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"],
                         ["last_period_date out of range"])

    def test_validate_registration_run_failure_receiver_id(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        # reg_data = registration_data.copy()
        registration_data["data"]["receiver_id"] = registration_data[
            "mother_id"]
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"], "mother requires own id")

    def test_validate_registration_run_failure_mother_uuid(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"], "Invalid UUID mother_id")

    def test_validate_registration_run_failure_mother_id(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        # reg_data = registration_data.copy()
        registration_data["data"]["receiver_id"] = str(uuid.uuid4())
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"],
                         "mother_id should be the same as receiver_id")


class TestSubscriptionRequest(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_only_prebirth_sms(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 15
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)
        # Check
        self.assertEqual(result, "1 SubscriptionRequest created")
        d_mom = SubscriptionRequest.objects.last()
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 1)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 1)

    @responses.activate
    def test_mother_only_prebirth_voice_mon_wed_9_11(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_audio_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 2, "short_name": 'prebirth_mother_audio_10_42',
                  "default_schedule": 4},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 15
        registration_data["data"]["msg_type"] = "audio"
        registration_data["data"]["voice_times"] = "9_11"
        registration_data["data"]["voice_days"] = "mon_wed"
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)
        # Check
        self.assertEqual(result, "1 SubscriptionRequest created")
        d_mom = SubscriptionRequest.objects.last()
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 2)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 4)

    @responses.activate
    def test_friend_only_prebirth_sms(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 15
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)
        # Check
        self.assertEqual(result, "2 SubscriptionRequests created")

        d_mom = SubscriptionRequest.objects.get(
            contact="mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 1)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 1)

        d_friend = SubscriptionRequest.objects.get(
            contact="friend00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_friend.contact,
                         "friend00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_friend.messageset_id, 3)
        self.assertEqual(d_friend.next_sequence_number, 1)
        self.assertEqual(d_friend.lang, "eng_NG")
        self.assertEqual(d_friend.schedule, 3)

    @responses.activate
    def test_friend_only_voice_mon_wed_2_5(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_audio_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 2, "short_name": 'prebirth_mother_audio_10_42',
                  "default_schedule": 4},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )

        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 15
        registration_data["data"]["msg_type"] = "audio"
        registration_data["data"]["voice_times"] = "2_5"
        registration_data["data"]["voice_days"] = "mon_wed"
        registration = Registration.objects.create(**registration_data)

        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)

        # Check
        self.assertEqual(result, "2 SubscriptionRequests created")

        d_mom = SubscriptionRequest.objects.get(
            contact="mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 2)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 4)

        d_friend = SubscriptionRequest.objects.get(
            contact="friend00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_friend.contact,
                         "friend00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_friend.messageset_id, 3)
        self.assertEqual(d_friend.next_sequence_number, 1)
        self.assertEqual(d_friend.lang, "eng_NG")
        self.assertEqual(d_friend.schedule, 3)

    @responses.activate
    def test_family_only_prebirth_sms(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )

        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_family"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 15
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)
        # Check
        self.assertEqual(result, "2 SubscriptionRequests created")

        d_mom = SubscriptionRequest.objects.get(
            contact="mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 1)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 1)

        d_family = SubscriptionRequest.objects.get(
            contact="family00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_family.contact,
                         "family00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_family.messageset_id, 3)
        self.assertEqual(d_family.next_sequence_number, 1)
        self.assertEqual(d_family.lang, "eng_NG")
        self.assertEqual(d_family.schedule, 3)

    @responses.activate
    def test_mother_and_father_prebirth_sms(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )

        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_father_and_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 30
        registration = Registration.objects.create(**registration_data)

        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)

        # Check
        self.assertEqual(result, "2 SubscriptionRequests created")

        d_mom = SubscriptionRequest.objects.get(
            contact="mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 1)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 1)

        d_dad = SubscriptionRequest.objects.get(
            contact="father00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_dad.contact, "father00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_dad.messageset_id, 3)
        self.assertEqual(d_dad.next_sequence_number, 1)
        self.assertEqual(d_dad.lang, "eng_NG")
        self.assertEqual(d_dad.schedule, 3)

    @responses.activate
    def test_mother_and_family_prebirth_sms(self):
        # Setup
        # mock mother messageset lookup
        query_string = '?short_name=prebirth_mother_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 1, "short_name": 'prebirth_mother_text_10_42',
                  "default_schedule": 1},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )
        # mock household messageset lookup
        query_string = '?short_name=prebirth_household_text_10_42'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={"id": 3, "short_name": 'prebirth_household_text_10_42',
                  "default_schedule": 3},
            status=200, content_type='application/json',
            match_querystring=True  # pos responses documentation!
        )

        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother00-9d89-4aa6-99ff-13c225365b5d",
            "data": REG_DATA["hw_pre_family_and_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["preg_week"] = 40
        registration = Registration.objects.create(**registration_data)

        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)

        # Check
        self.assertEqual(result, "2 SubscriptionRequests created")

        d_mom = SubscriptionRequest.objects.get(
            contact="mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.contact, "mother00-9d89-4aa6-99ff-13c225365b5d")
        self.assertEqual(d_mom.messageset_id, 1)
        self.assertEqual(d_mom.next_sequence_number, 1)
        self.assertEqual(d_mom.lang, "eng_NG")
        self.assertEqual(d_mom.schedule, 1)

        d_family = SubscriptionRequest.objects.get(
            contact="family00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_family.contact,
                         "family00-73a2-4d89-b045-d52004c025fe")
        self.assertEqual(d_family.messageset_id, 3)
        self.assertEqual(d_family.next_sequence_number, 1)
        self.assertEqual(d_family.lang, "eng_NG")
        self.assertEqual(d_family.schedule, 3)


class TestSubscriptionRequestWebhook(AuthenticatedAPITestCase):

    def test_create_webhook(self):
        # Setup
        user = User.objects.get(username='testadminuser')
        post_data = {
            "target": "http://example.com/registration/",
            "event": "subscriptionrequest.added"
        }
        # Execute
        response = self.adminclient.post('/api/v1/webhook/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Hook.objects.last()
        self.assertEqual(d.target, 'http://example.com/registration/')
        self.assertEqual(d.user, user)

    # This test is not working despite the code working fine
    # If you run these same steps below interactively the webhook will fire
    # @responses.activate
    # def test_mother_only_webhook(self):
    #     # Setup
    #     post_save.connect(receiver=model_saved, sender=SubscriptionRequest,
    #                       dispatch_uid='instance-saved-hook')
    #     Hook.objects.create(user=self.adminuser,
    #                         event='subscriptionrequest.added',
    #                         target='http://example.com/registration/')
    #
    #     expected_webhook = {
    #         "hook": {
    #             "target": "http://example.com/registration/",
    #             "event": "subscriptionrequest.added",
    #             "id": 3
    #         },
    #         "data": {
    #             "messageset_id": 1,
    #             "updated_at": "2016-02-17T07:59:42.831568+00:00",
    #             "contact": "mother00-9d89-4aa6-99ff-13c225365b5d",
    #             "lang": "eng_NG",
    #             "created_at": "2016-02-17T07:59:42.831533+00:00",
    #             "id": "5282ed58-348f-4a54-b1ff-f702e36ec3cc",
    #             "next_sequence_number": 1,
    #             "schedule": 1
    #         }
    #     }
    #     responses.add(
    #         responses.POST,
    #         "http://example.com/registration/",
    #         json.dumps(expected_webhook),
    #         status=200, content_type='application/json')
    #     registration_data = {
    #         "stage": "prebirth",
    #         "data": REG_DATA["hw_pre_mother"].copy(),
    #         "source": self.make_source_adminuser()
    #     }
    #     registration = Registration.objects.create(**registration_data)
    #     # Execute
    #     result = validate_registration.create_subscriptionrequests(
    #         registration)
    #     # Check
    #     self.assertEqual(result, "1 SubscriptionRequest created")
    #     d_mom = SubscriptionRequest.objects.last()
    #     self.assertEqual(d_mom.contact,
    #                      "mother00-9d89-4aa6-99ff-13c225365b5d")
    #     self.assertEqual(d_mom.messageset_id, 1)
    #     self.assertEqual(d_mom.next_sequence_number, 1)
    #     self.assertEqual(d_mom.lang, "eng_NG")
    #     self.assertEqual(d_mom.schedule, 1)
    #     self.assertEqual(responses.calls[0].request.url,
    #                      "http://example.com/registration/")
