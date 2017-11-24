import mock
import responses
import openpyxl
import os
from datetime import datetime

from django.contrib.auth.models import User
from django.core import mail
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from rest_hooks.models import model_saved
from seed_services_client import IdentityStoreApiClient, MessageSenderApiClient

from registrations.models import (
    Registration, Source, registration_post_save, fire_created_metric,
    fire_unique_operator_metric, fire_message_type_metric, fire_source_metric,
    fire_receiver_type_metric, fire_language_metric, fire_state_metric,
    fire_role_metric)
from reports.models import ReportTaskStatus
from reports.tasks.msisdn_message_report import generate_msisdn_message_report
from reports.utils import ExportWorkbook, generate_random_filename


class mockobj(object):
    @classmethod
    def choice(cls, li):
        return li[0]


@override_settings(
    IDENTITY_STORE_URL='http://identity-store/',
    IDENTITY_STORE_TOKEN='idstoretoken',
    MESSAGE_SENDER_URL='http://message-sender/',
    MESSAGE_SENDER_TOKEN='mstoken',
)
class GenerateReportTest(TestCase):
    def setUp(self):
        self.is_client = IdentityStoreApiClient('idstoretoken',
                                                'http://identity-store/')

        self.ms_client = MessageSenderApiClient('mstoken',
                                                'http://message-sender/')

        self.adminuser = User.objects.create()
        self.source = Source.objects.create(
            name='test_source', user=self.adminuser, authority='hw_full')

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

    def add_response_identity_store_search(self, msisdn, results):
        responses.add(
            responses.GET,
            ('http://identity-store/identities/search/'
                '?details__addresses__msisdn=%s' % msisdn),
            json={'results': results},
            content_type='application/json',
            match_querystring=True,
        )

    def add_response_get_identity(self, identity, result):
        responses.add(
            responses.GET,
            ('http://identity-store/identities/%s/' % identity),
            json=result,
            content_type='application/json',
            match_querystring=True,
        )

    def add_response_get_messages(self, identity, results):
        responses.add(
            responses.GET,
            ('http://message-sender/outbound/?to_identity=%s'
                '&after=2017-01-01T00:00:00'
                '&before=2018-01-01T00:00:00' % identity),
            json={'results': results},
            content_type='application/json',
            match_querystring=True,
        )


class PopulateSpreadsheetTest(GenerateReportTest):

    def test_populate_spreadsheet_returns_spreadsheet(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            [], {}, 0)
        self.assertTrue(isinstance(spreadsheet, ExportWorkbook))

    def test_populate_spreadsheet_has_headers_for_messages(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            [], {}, 2)

        self.assertEqual(
            spreadsheet._workbook.active['F1'].value, 'Message 1: content')
        self.assertEqual(
            spreadsheet._workbook.active['G1'].value, 'Message 1: date sent')
        self.assertEqual(
            spreadsheet._workbook.active['H1'].value, 'Message 1: status')
        self.assertEqual(
            spreadsheet._workbook.active['I1'].value, 'Message 2: content')
        self.assertEqual(
            spreadsheet._workbook.active['J1'].value, 'Message 2: date sent')
        self.assertEqual(
            spreadsheet._workbook.active['K1'].value, 'Message 2: status')

    def test_populate_spreadsheet_skips_if_identity_is_missing(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            ['+2340000000'],
            {"+2340000000": {
                "reg_date": "2017-01-01 00:00:00",
                "facility": "Somewhere",
                "preg_week": 16,
                "msg_type": "text"
            }}, 0)

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['B2'].value, None)
        self.assertEqual(
            spreadsheet._workbook.active['C2'].value, None)

    def test_populate_spreadsheet_includes_registration_details(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            ['+2340000000'],
            {"+2340000000": {
                "id": "54cc71b7-533f-4a83-93c1-e02340000000",
                "reg_date": "2017-01-01 00:00:00",
                "facility": "Somewhere",
                "preg_week": 16,
                "msg_type": "text"
            }}, 0)

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['B2'].value, "2017-01-01 00:00:00")
        self.assertEqual(
            spreadsheet._workbook.active['C2'].value, 'Somewhere')
        self.assertEqual(
            spreadsheet._workbook.active['D2'].value, 16)
        self.assertEqual(
            spreadsheet._workbook.active['E2'].value, 'text')
        self.assertEqual(
            spreadsheet._workbook.active['F2'].value, None)

    def test_populate_spreadsheet_includes_messages(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            ['+2340000000'],
            {"+2340000000": {
                "id": "54cc71b7-533f-4a83-93c1-e02340000000",
                "messages": [{
                    "content": "Test message",
                    "date_sent": "2017-01-01 00:00:00",
                    "status": "Delivered"
                }, {
                    "content": "Another test message",
                    "date_sent": "2017-01-02 00:00:00",
                    "status": "Undelivered"
                }]
            }}, 2)

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['D2'].value, '')
        self.assertEqual(
            spreadsheet._workbook.active['F2'].value, 'Test message')
        self.assertEqual(
            spreadsheet._workbook.active['G2'].value, "2017-01-01 00:00:00")
        self.assertEqual(
            spreadsheet._workbook.active['H2'].value, 'Delivered')
        self.assertEqual(
            spreadsheet._workbook.active['I2'].value, 'Another test message')
        self.assertEqual(
            spreadsheet._workbook.active['J2'].value, "2017-01-02 00:00:00")
        self.assertEqual(
            spreadsheet._workbook.active['K2'].value, 'Undelivered')

    def test_populate_spreadsheet_maintains_order(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            ['+2340000000', '+2341111111', '+2342222222'],
            {"+2340000000": {}, "+2342222222": {}, "+2341111111": {}}, 0)

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['A3'].value, '+2341111111')
        self.assertEqual(
            spreadsheet._workbook.active['A4'].value, '+2342222222')


class RetrieveIdentityInfoTest(GenerateReportTest):

    @responses.activate
    def test_retrieve_identity_adds_id(self):
        self.add_response_identity_store_search('%2B2340000000', [
            {'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-01T00:00:00.000000Z'}])

        data = generate_msisdn_message_report.retrieve_identity_info(
            self.is_client, ['+2340000000'])

        self.assertDictEqual(data['+2340000000'], {
            'id': '54cc71b7-533f-4a83-93c1-e02340000000',
            'created_at': '2017-01-01T00:00:00.000000Z'})

    @responses.activate
    def test_retrieve_identity_works_with_multiple_msisdns(self):
        self.add_response_identity_store_search('%2B2340000000', [
            {'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-01T00:00:00.000000Z'}])
        self.add_response_identity_store_search('%2B2341111111', [
            {'id': '54cc71b7-533f-4a83-93c1-e02341111111',
                'created_at': '2017-01-02T00:00:00.000000Z'}])

        data = generate_msisdn_message_report.retrieve_identity_info(
            self.is_client, ['+2340000000', '+2341111111'])

        self.assertDictEqual(data['+2340000000'], {
            'id': '54cc71b7-533f-4a83-93c1-e02340000000',
            'created_at': '2017-01-01T00:00:00.000000Z'})
        self.assertDictEqual(data['+2341111111'], {
            'id': '54cc71b7-533f-4a83-93c1-e02341111111',
            'created_at': '2017-01-02T00:00:00.000000Z'})

    @responses.activate
    def test_identity_data_empty_if_none_found(self):
        self.add_response_identity_store_search('%2B2340000000', [])

        data = generate_msisdn_message_report.retrieve_identity_info(
            self.is_client, ['+2340000000'])

        self.assertEqual(data['+2340000000'], {})

    @responses.activate
    def test_identity_data_empty_if_multiple_found(self):
        self.add_response_identity_store_search('%2B2340000000', [
            {'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-01T00:00:00.000000Z'},
            {'id': '54cc71b7-533f-4a83-93c1-e02341111111',
                'created_at': '2017-01-02T00:00:00.000000Z'}])

        data = generate_msisdn_message_report.retrieve_identity_info(
            self.is_client, ['+2340000000'])

        self.assertEqual(data['+2340000000'], {})


class RetrieveRegistrationInfoTest(GenerateReportTest):

    def test_get_registration_data_skipped_if_no_identity(self):
        data = generate_msisdn_message_report.retrieve_registration_info(
            self.is_client, {'+2340000000': {}}
        )

        self.assertEqual(data['+2340000000'], {})

    def test_get_registration_data_skipped_if_no_registration(self):
        data = generate_msisdn_message_report.retrieve_registration_info(
            self.is_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-02T00:00:00.000000Z'}})

        self.assertDictEqual(data['+2340000000'], {
            'id': '54cc71b7-533f-4a83-93c1-e02340000000',
            'created_at': '2017-01-02T00:00:00.000000Z'})

    def test_get_registration_data_without_operator(self):
        reg = Registration.objects.create(
            source=self.source, data={'msg_type': 'text', 'preg_week': 16},
            mother_id='54cc71b7-533f-4a83-93c1-e02340000000')

        data = generate_msisdn_message_report.retrieve_registration_info(
            self.is_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-02T00:00:00.000000Z'}})

        self.assertDictEqual(data['+2340000000'], {
            'id': '54cc71b7-533f-4a83-93c1-e02340000000',
            'created_at': '2017-01-02T00:00:00.000000Z',
            'reg_date': reg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'msg_type': 'text', 'preg_week': 16, 'facility': ''})

    @responses.activate
    def test_get_registration_data_with_operator(self):
        self.add_response_get_identity(
            '54cc71b7-533f-4a83-93c1-e02341111111', {
                'id': '54cc71b7-533f-4a83-93c1-e02341111111', 'details': {
                    'facility_name': 'Somewhere'
                }
            })

        reg = Registration.objects.create(
            source=self.source, data={
                'msg_type': 'text', 'preg_week': 16,
                'operator_id': '54cc71b7-533f-4a83-93c1-e02341111111'},
            mother_id='54cc71b7-533f-4a83-93c1-e02340000000')

        data = generate_msisdn_message_report.retrieve_registration_info(
            self.is_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000',
                'created_at': '2017-01-02T00:00:00.000000Z'}})

        self.assertDictEqual(data['+2340000000'], {
            'id': '54cc71b7-533f-4a83-93c1-e02340000000',
            'created_at': '2017-01-02T00:00:00.000000Z',
            'reg_date': reg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'msg_type': 'text', 'preg_week': 16, 'facility': 'Somewhere'})


class RetrieveMessagesTest(GenerateReportTest):

    def test_get_messages_skipped_if_no_identity(self):
        (data, _) = generate_msisdn_message_report.retrieve_messages(
            self.ms_client, {'+2340000000': {}},
            datetime(2017, 1, 1), datetime(2018, 1, 1)
        )

        self.assertEqual(data['+2340000000'], {})

    @responses.activate
    def test_get_messages_skipped_if_no_messages(self):
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02340000000', [])

        (data, _) = generate_msisdn_message_report.retrieve_messages(
            self.ms_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000'}},
            datetime(2017, 1, 1), datetime(2018, 1, 1)
        )

        self.assertEqual(data['+2340000000']['messages'], [])

    @responses.activate
    def test_get_messages_handles_voice_urls(self):
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02340000000', [
                {'content': None, 'delivered': True,
                 'created_at': '2017-01-01T00:00:00.000000Z',
                 'metadata': {
                    'voice_speech_url': 'http://registration/voice_url_1.mp3'
                 }},
                {'content': None, 'delivered': True,
                 'created_at': '2017-01-02T00:00:00.000000Z',
                 'metadata': {
                    'voice_speech_url': ['http://registration/voice_url_1.mp3',
                                         'http://registration/voice_url_2.mp3']
                 }}
            ])

        (data, _) = generate_msisdn_message_report.retrieve_messages(
            self.ms_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000'}},
            datetime(2017, 1, 1), datetime(2018, 1, 1)
        )

        self.assertEqual(data['+2340000000']['messages'], [
            {'content': 'http://registration/voice_url_1.mp3',
             'status': 'Delivered', 'date_sent': "2017-01-01 00:00:00"},
            {'content': 'http://registration/voice_url_1.mp3, '
                        'http://registration/voice_url_2.mp3',
             'status': 'Delivered', 'date_sent': "2017-01-02 00:00:00"}
        ])

    @responses.activate
    def test_get_messages_multiple_messages(self):
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02340000000', [
                {'content': 'message 1', 'delivered': True,
                 'created_at': '2017-01-02T00:00:00.000000Z'},
                {'content': 'message 2', 'delivered': False,
                 'created_at': '2017-01-03T00:00:00.000000Z'}
            ])

        (data, length) = generate_msisdn_message_report.retrieve_messages(
            self.ms_client, {'+2340000000': {
                'id': '54cc71b7-533f-4a83-93c1-e02340000000'}},
            datetime(2017, 1, 1), datetime(2018, 1, 1)
        )

        self.assertEqual(length, 2)
        self.assertEqual(data['+2340000000']['messages'], [
            {'content': 'message 1', 'status': 'Delivered',
             'date_sent': "2017-01-02 00:00:00"},
            {'content': 'message 2', 'status': 'Undelivered',
             'date_sent': "2017-01-03 00:00:00"}
        ])

    @responses.activate
    def test_get_messages_returns_longest_list_length(self):
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02340000000', [
                {'content': 'message 1', 'delivered': True,
                 'created_at': '2017-01-02T00:00:00.000000Z'},
                {'content': 'message 2', 'delivered': False,
                 'created_at': '2017-01-03T00:00:00.000000Z'}
            ])
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02341111111', [
                {'content': 'message 3', 'delivered': True,
                 'created_at': '2017-01-04T00:00:00.000000Z'}
            ])

        (data, length) = generate_msisdn_message_report.retrieve_messages(
            self.ms_client, {
                '+2340000000': {
                    'id': '54cc71b7-533f-4a83-93c1-e02340000000'},
                '+2341111111': {
                    'id': '54cc71b7-533f-4a83-93c1-e02341111111'}},
            datetime(2017, 1, 1), datetime(2018, 1, 1)
        )

        self.assertEqual(length, 2)
        self.assertEqual(data['+2340000000']['messages'], [
            {'content': 'message 1', 'status': 'Delivered',
             'date_sent': "2017-01-02 00:00:00"},
            {'content': 'message 2', 'status': 'Undelivered',
             'date_sent': "2017-01-03 00:00:00"}
        ])
        self.assertEqual(data['+2341111111']['messages'], [
            {'content': 'message 3', 'status': 'Delivered',
             'date_sent': "2017-01-04 00:00:00"}
        ])


class GenerateMSISDNMessageReportTest(GenerateReportTest):

    def trigger_report_generation(self, msisdns=[], emails=[]):
        with mock.patch('random.choice', mockobj.choice):
            filename = generate_random_filename()

            task_status = ReportTaskStatus.objects.create(**{
                "start_date": '2017-01-01',
                "end_date": '2018-01-01',
                "email_subject": 'The Email Subject',
                "status": ReportTaskStatus.PENDING
            })

            generate_msisdn_message_report.apply_async(kwargs={
                'start_date': '2017-01-01',
                'end_date': '2018-01-01',
                'email_recipients': emails,
                'email_subject': 'The Email Subject',
                'task_status_id': task_status.id,
                'msisdns': msisdns
            })

            return filename

    @responses.activate
    @mock.patch("os.remove")
    def test_generate_report_email(self, mock_remove):
        """
        Generating a report should create an email with the correct address,
        subject, and attachment.
        """

        self.add_response_identity_store_search('%2B2340000000', [])
        self.trigger_report_generation(['+2340000000'], ['foo@example.com'])
        [report_email] = mail.outbox
        self.assertEqual(report_email.subject, 'The Email Subject')
        (file_name, data, mimetype) = report_email.attachments[0]
        self.assertEqual('msisdn-report-2017-01-01-to-2018-01-01.xlsx',
                         file_name)

    @responses.activate
    def test_generate_report_status_done_with_email(self):
        """
        Generating a report should mark the ReportTaskStatus objects as Done if
        it is successful.
        """

        self.add_response_identity_store_search('%2B2340000000', [])
        self.trigger_report_generation(['+2340000000'], ['foo@example.com'])

        task_status = ReportTaskStatus.objects.last()
        self.assertEqual(task_status.status, ReportTaskStatus.DONE)
        self.assertEqual(task_status.file_size > 5000, True)

    @mock.patch("reports.tasks.send_email.SendEmail.apply_async")
    @responses.activate
    def test_generate_report_status_email(self, mock_send):
        """
        Generating a report should mark the ReportTaskStatus objects as Sending
        before it sends the email.
        """

        self.add_response_identity_store_search('%2B2340000000', [])
        self.trigger_report_generation(['+2340000000'], ['foo@example.com'])

        task_status = ReportTaskStatus.objects.last()
        self.assertEqual(task_status.status, ReportTaskStatus.SENDING)
        self.assertEqual(task_status.file_size > 5000, True)

    @responses.activate
    def test_generate_report_status_done_without_email(self):
        """
        Generating a report should mark the ReportTaskStatus objects as Done
        if no email_recipients are specified.
        """

        self.add_response_identity_store_search('%2B2340000000', [])
        self.trigger_report_generation(['+2340000000'])

        task_status = ReportTaskStatus.objects.last()
        self.assertEqual(task_status.status, ReportTaskStatus.DONE)
        self.assertEqual(task_status.file_size > 5000, True)

    @responses.activate
    @mock.patch("reports.tasks.send_email.SendEmail.apply_async")
    def test_generate_report_status_running(self, mock_send):
        """
        Generating a report should mark the ReportTaskStatus objects as Running
        while the generation is in progress.
        """

        orig = openpyxl.Workbook.save

        mock_called = {'ran': False}

        def new_save(wb, file):
            task_status = ReportTaskStatus.objects.last()
            self.assertEqual(task_status.status, ReportTaskStatus.RUNNING)
            orig(wb, file)
            mock_called['ran'] = True

        self.add_response_identity_store_search('%2B2340000000', [])

        with mock.patch('openpyxl.Workbook.save', new_save):
            self.trigger_report_generation(['+2340000000'])
        self.assertTrue(mock_called['ran'])

    @responses.activate
    @override_settings(
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=False)
    def test_generate_report_status_failed(self):
        """
        Generating a report should mark the ReportTaskStatus objects as Failed
        if there is a problem.
        """

        self.add_response_identity_store_search('%2B2340000000', [])

        task_status = ReportTaskStatus.objects.create(**{
            "start_date": "not_really_a_date",
            "end_date": '2018-01-01',
            "email_subject": 'The Email Subject',
            "status": ReportTaskStatus.PENDING
        })

        try:
            with mock.patch('random.choice', mockobj.choice):
                generate_msisdn_message_report.apply_async(kwargs={
                    'start_date': "not_really_a_date",
                    'end_date': datetime.strptime('2018-01-01', '%Y-%m-%d'),
                    'email_recipients': ['foo@example.com'],
                    'email_subject': 'The Email Subject',
                    'task_status_id': task_status.id})
        except:
            pass

        task_status.refresh_from_db()
        self.assertEqual(task_status.status, ReportTaskStatus.FAILED)
        self.assertEqual(task_status.error,
                         "time data 'not_really_a_date' does not match format "
                         "'%Y-%m-%d'")

    @responses.activate
    def test_generate_full_report(self):
        # msisdn without identity
        self.add_response_identity_store_search('%2B2340000000', [])
        # msisdn without registration
        self.add_response_identity_store_search('%2B2341111111', [
            {'id': '54cc71b7-533f-4a83-93c1-e02341111111',
                'created_at': '2017-01-01T00:00:00.000000Z'}])
        # msisdn without messages
        self.add_response_identity_store_search('%2B2342222222', [
            {'id': '54cc71b7-533f-4a83-93c1-e02342222222',
                'created_at': '2017-01-02T00:00:00.000000Z'}])
        # msisdn with varying multiple messages
        self.add_response_identity_store_search('%2B2343333333', [
            {'id': '54cc71b7-533f-4a83-93c1-e02343333333',
                'created_at': '2017-01-02T00:00:00.000000Z'}])

        self.add_response_get_identity('54cc71b7-533f-4a83-93c1-e0235555555', {
            'details': {
                'facility_name': 'Somewhere'}
            })

        reg1 = Registration.objects.create(
            source=self.source, data={
                'msg_type': 'text', 'preg_week': 1,
                'operator_id': '54cc71b7-533f-4a83-93c1-e0235555555'},
            mother_id='54cc71b7-533f-4a83-93c1-e02342222222')
        reg2 = Registration.objects.create(
            source=self.source, data={'msg_type': 'text', 'preg_week': 2},
            mother_id='54cc71b7-533f-4a83-93c1-e02343333333')

        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02341111111', [
                {'content': 'message 0', 'delivered': True,
                 'created_at': '2017-01-02T00:00:00.000000Z'}
            ])
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02342222222', [])
        self.add_response_get_messages(
            '54cc71b7-533f-4a83-93c1-e02343333333', [
                {'content': 'message 1', 'delivered': True,
                 'created_at': '2017-01-02T00:00:00.000000Z'},
                {'content': 'message 2', 'delivered': False,
                 'created_at': '2017-01-03T00:00:00.000000Z'}
            ])

        orig = openpyxl.Workbook.save

        mock_called = {'ran': False}

        def new_save(wb, file):
            sheet = wb['Data for study cohort']
            self.assertEqual(sheet['A1'].value, 'Phone number')
            self.assertEqual(sheet['B1'].value, 'Date registered')
            self.assertEqual(sheet['C1'].value, 'Facility')
            self.assertEqual(sheet['D1'].value, 'Pregnancy week')
            self.assertEqual(sheet['E1'].value, 'Message type')
            self.assertEqual(sheet['F1'].value, 'Message 1: content')
            self.assertEqual(sheet['G1'].value, 'Message 1: date sent')
            self.assertEqual(sheet['H1'].value, 'Message 1: status')
            self.assertEqual(sheet['I1'].value, 'Message 2: content')
            self.assertEqual(sheet['J1'].value, 'Message 2: date sent')
            self.assertEqual(sheet['K1'].value, 'Message 2: status')

            self.assertEqual(sheet['A2'].value, '+2340000000')
            self.assertEqual(sheet['B2'].value, None)
            self.assertEqual(sheet['C2'].value, None)
            self.assertEqual(sheet['D2'].value, None)
            self.assertEqual(sheet['E2'].value, None)

            self.assertEqual(sheet['A3'].value, '+2341111111')
            self.assertEqual(sheet['B3'].value, '')
            self.assertEqual(sheet['C3'].value, '')
            self.assertEqual(sheet['D3'].value, '')
            self.assertEqual(sheet['E3'].value, '')
            self.assertEqual(sheet['F3'].value, 'message 0')
            self.assertEqual(sheet['G3'].value, "2017-01-02 00:00:00")
            self.assertEqual(sheet['H3'].value, 'Delivered')

            self.assertEqual(sheet['A4'].value, '+2342222222')
            self.assertEqual(sheet['B4'].value,
                             reg1.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            self.assertEqual(sheet['C4'].value, 'Somewhere')
            self.assertEqual(sheet['D4'].value, 1)
            self.assertEqual(sheet['E4'].value, 'text')
            self.assertEqual(sheet['F4'].value, None)

            self.assertEqual(sheet['A5'].value, '+2343333333')
            self.assertEqual(sheet['B5'].value,
                             reg2.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            self.assertEqual(sheet['C5'].value, '')
            self.assertEqual(sheet['D5'].value, 2)
            self.assertEqual(sheet['E5'].value, 'text')
            self.assertEqual(sheet['F5'].value, 'message 1')
            self.assertEqual(sheet['G5'].value, "2017-01-02 00:00:00")
            self.assertEqual(sheet['H5'].value, 'Delivered')
            self.assertEqual(sheet['I5'].value, 'message 2')
            self.assertEqual(sheet['J5'].value, "2017-01-03 00:00:00")
            self.assertEqual(sheet['K5'].value, 'Undelivered')

            orig(wb, file)
            mock_called['ran'] = True

        with mock.patch('openpyxl.Workbook.save', new_save):
            self.trigger_report_generation([
                '+2340000000', '+2341111111', '+2342222222', '+2343333333'])

        self.assertTrue(mock_called['ran'])
