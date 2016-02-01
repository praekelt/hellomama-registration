import json
import uuid
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.db.models.signals import post_save
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Source, Registration, registration_post_save
from .tasks import (
    validate_registration,
    is_valid_date, is_valid_uuid, is_valid_lang, is_valid_msg_type,
    is_valid_msg_receiver, is_valid_loss_reason, is_valid_name,
    is_valid_id_type, is_valid_id_no)
from registrations import tasks


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


REG_FIELDS = {
    "hw_pre_id": [
        "contact", "registered_by", "language", "msg_type",
        "last_period_date", "msg_receiver", "hoh_name", "hoh_surname",
        "mama_name", "mama_surname", "mama_id_type", "mama_id_no"],
}

REG_DATA = {
    "hw_pre_id": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
    },
    "hw_pre_dob": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "other",
        "mama_dob": "19900707"
    },
    "hw_post_id": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "baby_dob": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
    },
    "hw_post_dob": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "baby_dob": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "other",
        "mama_dob": "19900707"
    },
    "pbl_pre": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend"
    },
    "pbl_loss": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "loss_reason": "miscarriage"
    },
    "bad_data_combination": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
    },
    "bad_fields": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "2015020",
        "msg_receiver": "trusted friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
    },
    "bad_lmp": {
        "contact": str(uuid.uuid4()),
        "registered_by": str(uuid.uuid4()),
        "language": "english",
        "msg_type": "sms",
        "last_period_date": "20140202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
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
        post_save.disconnect(registration_post_save, sender=Registration)
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
        valid_lang = "runyakore"
        invalid_lang = "french"
        # Execute
        # Check
        self.assertEqual(is_valid_lang(valid_lang), True)
        self.assertEqual(is_valid_lang(invalid_lang), False)

    def test_is_valid_msg_type(self):
        # Setup
        valid_msg_type = "sms"
        invalid_msg_type = "voice"
        # Execute
        # Check
        self.assertEqual(is_valid_msg_type(valid_msg_type), True)
        self.assertEqual(is_valid_msg_type(invalid_msg_type), False)

    def test_is_valid_msg_receiver(self):
        # Setup
        valid_msg_receiver = "head_of_household"
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

    def test_is_valid_name(self):
        # Setup
        valid_name1 = "Namey"
        valid_name2 = "Zoé"
        valid_name3 = "1234"
        invalid_name = 10375075
        # Execute
        # Check
        self.assertEqual(is_valid_name(valid_name1), True)
        self.assertEqual(is_valid_name(valid_name2), True)
        self.assertEqual(is_valid_name(valid_name3), True)  # TODO reject
        self.assertEqual(is_valid_name(invalid_name), False)

    def test_is_valid_id_type(self):
        # Setup
        valid_id_type = "ugandan_id"
        invalid_id_type = "sa_id"
        # Execute
        # Check
        self.assertEqual(is_valid_id_type(valid_id_type), True)
        self.assertEqual(is_valid_id_type(invalid_id_type), False)

    def test_is_valid_id_no(self):
        # Setup
        valid_id_no = "12345"
        invalid_id_no = 12345
        # Execute
        # Check
        self.assertEqual(is_valid_id_no(valid_id_no), True)
        self.assertEqual(is_valid_id_no(invalid_id_no), False)

    def test_check_field_values(self):
        # Setup
        valid_hw_pre_id_registration_data = REG_DATA["hw_pre_id"]
        invalid_hw_pre_id_registration_data = REG_DATA["hw_pre_id"].copy()
        invalid_hw_pre_id_registration_data["msg_receiver"] = "somebody"
        # Execute
        cfv_valid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_id"], valid_hw_pre_id_registration_data)
        cfv_invalid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_id"], invalid_hw_pre_id_registration_data)
        # Check
        self.assertEqual(cfv_valid, [])
        self.assertEqual(cfv_invalid, ['msg_receiver'])


class TestRegistrationValidation(AuthenticatedAPITestCase):

    def test_validate_hw_prebirth_id(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["hw_pre_id"],
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_id")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_dob(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["hw_pre_dob"],
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_dob")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_postbirth_id(self):
        # Setup
        registration_data = {
            "stage": "postbirth",
            "data": REG_DATA["hw_post_id"],
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_post_id")
        self.assertEqual(registration.data["baby_age"], 1)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_postbirth_dob(self):
        # Setup
        registration_data = {
            "stage": "postbirth",
            "data": REG_DATA["hw_post_dob"],
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_post_dob")
        self.assertEqual(registration.data["baby_age"], 1)
        self.assertEqual(registration.validated, True)

    def test_validate_pbl_prebirth(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["pbl_pre"],
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_pbl_loss(self):
        # Setup
        registration_data = {
            "stage": "loss",
            "data": REG_DATA["pbl_loss"],
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
            "data": REG_DATA["hw_pre_id"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20130101"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_pregnancy_too_short(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["hw_pre_id"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20150816"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_registration_run_success(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["hw_pre_id"],
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Success")

    def test_validate_registration_run_failure_bad_combination(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "data": REG_DATA["bad_data_combination"],
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
            "data": REG_DATA["bad_fields"],
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
            "data": REG_DATA["bad_lmp"],
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
