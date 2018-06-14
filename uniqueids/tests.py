import json
import os
import responses

try:
    import mock
except ImportError:
    from unittest import mock

from django.test import TestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved

from .models import (
    Record, record_post_save, PersonnelUpload, State, Facility, Community)
from .tasks import add_unique_id_to_identity, send_personnel_code


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

    @mock.patch("uniqueids.tasks.add_unique_id_to_identity.s")
    @mock.patch("uniqueids.tasks.send_personnel_code")
    def test_record_post_save_not_send_code(self, mock_send_code, mock_add_id):
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "health_id"
        }
        # Execute
        record = Record.objects.create(**data)

        record_post_save(Record, record, True)

        mock_add_id.assert_called_once_with(identity=str(
            record.identity), unique_id=record.id, write_to="health_id")
        mock_send_code.assert_not_called()

    @mock.patch("uniqueids.tasks.add_unique_id_to_identity.s")
    @mock.patch("uniqueids.tasks.send_personnel_code.si")
    def test_record_post_save_send_code(self, mock_send_code, mock_add_id):
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "personnel_code"
        }
        # Execute
        record = Record.objects.create(**data)

        record_post_save(Record, record, True)

        mock_add_id.assert_called_once_with(identity=str(
            record.identity), unique_id=record.id, write_to="personnel_code")
        mock_send_code.assert_called_once_with(identity=str(
            record.identity), personnel_code=record.id)


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

    @responses.activate
    def test_send_personnel_code(self):
        """
        The task should attempt to send a message to the identity, with the
        generated personnel code.
        """
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/70097580-c9fe-4f92-a55e-'
            '8f5f54b19799/addresses/msisdn?default=True',
            json={
                'results': [
                    {'address': '+27123456789'},
                ],
            },
            content_type='application/json', match_querystring=True
        )
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            body='{}',
            content_type='application/json'
        )

        result = send_personnel_code.delay(
            '70097580-c9fe-4f92-a55e-8f5f54b19799', 1234567890)

        self.assertEqual(
            result.get(),
            "Sent personnel code to 70097580-c9fe-4f92-a55e-8f5f54b19799. "
            "Result: {}")

        [_, message_send] = responses.calls
        self.assertEqual(json.loads(message_send.request.body), {
            'to_addr': '+27123456789',
            'content': (
                'Welcome to HelloMama. You have been registered as a HCW. '
                'Dial 55500 to start registering mothers. Your personnel '
                'code is 1234567890.'),
            'metadata': {},
        })


class TestRecordAdmin(AuthenticatedAPITestCase):
    def setUp(self):
        super(TestRecordAdmin, self).setUp()
        self.adminclient.login(username=self.adminusername,
                               password=self.adminpassword)

    @mock.patch("uniqueids.tasks.send_personnel_code.apply_async")
    def test_resend_personnel_code_only_selected(self, mock_send_code):
        record1 = Record.objects.create(
            identity="9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            write_to="personnel_code")
        Record.objects.create(
            identity="c304f463-6db4-4f89-a095-46319da06ac9",
            write_to="personnel_code"
        )
        data = {'action': 'resend_personnel_code',
                '_selected_action': [record1.pk]}

        response = self.adminclient.post(
            reverse('admin:uniqueids_record_changelist'), data, follow=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "1 Record was resent.")

        mock_send_code.assert_called_once_with(kwargs={"identity": str(
            record1.identity), "personnel_code": record1.id})

    @mock.patch("uniqueids.tasks.send_personnel_code.apply_async")
    def test_resend_personnel_code_multiple(self, mock_send_code):
        record1 = Record.objects.create(
            identity="9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            write_to="personnel_code")
        record2 = Record.objects.create(
            identity="c304f463-6db4-4f89-a095-46319da06ac9",
            write_to="personnel_code"
        )
        data = {'action': 'resend_personnel_code',
                '_selected_action': [record1.pk, record2.pk]}

        response = self.adminclient.post(
            reverse('admin:uniqueids_record_changelist'), data, follow=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "2 Records were resent.")

        mock_send_code.assert_any_call(kwargs={"identity": str(
            record1.identity), "personnel_code": record1.id})
        mock_send_code.assert_any_call(kwargs={"identity": str(
            record2.identity), "personnel_code": record2.id})

    @mock.patch("uniqueids.tasks.send_personnel_code.apply_async")
    def test_resend_personnel_code_only_hcw(self, mock_send_code):
        record1 = Record.objects.create(
            identity="9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            write_to="personnel_code")
        record2 = Record.objects.create(
            identity="c304f463-6db4-4f89-a095-46319da06ac9",
            write_to="health_id"
        )
        data = {'action': 'resend_personnel_code',
                '_selected_action': [record1.pk, record2.pk]}

        response = self.adminclient.post(
            reverse('admin:uniqueids_record_changelist'), data, follow=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "1 Record was resent.")

        mock_send_code.assert_called_once_with(kwargs={"identity": str(
            record1.identity), "personnel_code": record1.id})


class TestPersonnelUploadAdmin(AuthenticatedAPITestCase):
    def setUp(self):
        super(TestPersonnelUploadAdmin, self).setUp()
        self.adminclient.login(username=self.adminusername,
                               password=self.adminpassword)

        State.objects.create(name="Test State")
        Facility.objects.create(name="Test Facility")
        Community.objects.create(name="Test Community")

    def mock_identity_post(self, identity_id):
        responses.add(
            responses.POST,
            'http://localhost:8001/api/v1/identities/',
            json={
                "id": identity_id,
                "details": {}
            },

        )

    def mock_identity_lookup(self, msisdn, field="msisdn", results=[]):
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/search/?details__addresses__{}={}'.format(field, msisdn.replace('+', '%2B')),  # noqa
            json={
                "next": None, "previous": None,
                "results": results
            },
            status=200, content_type='application/json',
            match_querystring=True
        )

    def create_file(self, detail):
        standard = {
            "address_type": "msisdn",
            "address": "0701231234",
            "preferred_language": "eng_NG",
            "receiver_role": "health care worker",
            "uniqueid_field_length": "5",
            "name": "Peter",
            "surname": "Pan"
        }

        standard.update(detail)

        return SimpleUploadedFile(
            "import.csv", '{}\n{}'.format(
                ','.join(standard.keys()),
                ','.join(standard.values())).encode())

    def test_personnel_upload_no_rows(self):
        csv_file = SimpleUploadedFile(
            'import.csv', 'these are the file contents!'.encode())

        data = {"csv_file": csv_file,
                "import_type": PersonnelUpload.PERSONNEL_TYPE}

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error, "No Rows")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_invalid_data(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "personnel_code",
            "facility_name": "Another Facility",
            "state": "Another State",
            "role": "CHEW"
        })

        data = {"csv_file": csv_file,
                "import_type": PersonnelUpload.PERSONNEL_TYPE}

        self.mock_identity_lookup("+234701231234")

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error, "Invalid States: Another State, Invalid"
                         " Facilities: Another Facility")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_missing_fields(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "corp_code"
        })

        data = {"csv_file": csv_file, "import_type": PersonnelUpload.CORP_TYPE}

        self.mock_identity_lookup("+234701231234")

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error, "Missing fields: community")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_missing_values(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "corp_code",
            "community": "Test Community",
            "name": ""
        })

        data = {"csv_file": csv_file, "import_type": PersonnelUpload.CORP_TYPE}

        self.mock_identity_lookup("+234701231234")

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error, "Missing or invalid values: name")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_existing_address(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "corp_code",
            "community": "Test Community",
        })

        data = {"csv_file": csv_file, "import_type": PersonnelUpload.CORP_TYPE}

        self.mock_identity_lookup("+234701231234", results=[{"id": "test"}])

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error,
                         "Address invalid or already exists: 0701231234")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_invalid_address(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "corp_code",
            "community": "Test Community",
            "msisdn": "123"
        })

        data = {"csv_file": csv_file, "import_type": PersonnelUpload.CORP_TYPE}

        self.mock_identity_lookup("+234701231234", results=[{"id": "test"}])

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        self.assertEqual(upload.error,
                         "Address invalid or already exists: 0701231234")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_invalid_values(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "wrong_code",
            "community": "Test Community",
            "address_type": "email",
            "preferred_language": "klingon",
            "uniqueid_field_length": "long",
        })

        data = {"csv_file": csv_file, "import_type": PersonnelUpload.CORP_TYPE}

        self.mock_identity_lookup("+234701231234", field="email")

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertFalse(upload.valid)
        print(upload.error)
        self.assertEqual(
            upload.error, "Missing or invalid values: address_type, "
            "preferred_language, uniqueid_field_length, uniqueid_field_name")

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))

    @responses.activate
    def test_personnel_upload_good(self):
        csv_file = self.create_file({
            "uniqueid_field_name": "personnel_code",
            "facility_name": "Test Facility",
            "state": "Test State",
            "role": "CHEW"
        })

        data = {"csv_file": csv_file,
                "import_type": PersonnelUpload.PERSONNEL_TYPE}

        self.mock_identity_post("test-id-personnel")
        self.mock_identity_lookup("+234701231234")

        self.adminclient.post(
            reverse('admin:uniqueids_personnelupload_add'), data, follow=True)

        upload = PersonnelUpload.objects.first()
        self.assertTrue(upload.valid)
        self.assertEqual(upload.error, "")

        [_, identity_post] = responses.calls
        self.assertEqual(
            json.loads(identity_post.request.body),
            {
                'communicate_through': None,
                'details': {
                    'addresses': {'msisdn': {'0701231234': {"default": True}}},
                    'default_addr_type': 'msisdn',
                    'facility_name': 'Test Facility',
                    'name': 'Peter',
                    'preferred_language': 'eng_NG',
                    'receiver_role': 'health care worker',
                    'role': 'CHEW',
                    'state': 'Test State',
                    'surname': 'Pan',
                    'uniqueid_field_length': '5',
                    'uniqueid_field_name': 'personnel_code'
                }
            })

        filepath = '{}/{}'.format(settings.MEDIA_ROOT, upload.csv_file)
        self.assertFalse(os.path.exists(filepath))
