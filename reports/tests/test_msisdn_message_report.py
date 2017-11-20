import responses
from datetime import datetime

from django.test import TestCase, override_settings
from reports.tasks.msisdn_message_report import generate_msisdn_message_report
from reports.utils import ExportWorkbook


@override_settings(
    IDENTITY_STORE_URL='http://identity-store/',
    IDENTITY_STORE_TOKEN='idstoretoken',
)
class GenerateMSISDNMessageReportTest(TestCase):
    def add_response_identity_store_search(self, results):
        responses.add(
            responses.GET,
            ('http://identity-store/identities/search/'
                '?details__addresses__msisdn=%2B2340000000'),
            json={'results': results},
            content_type='application/json',
            match_querystring=True,
        )

    def test_populate_spreadsheet_returns_spreadsheet(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            {}, 0)
        self.assertTrue(isinstance(spreadsheet, ExportWorkbook))

    def test_populate_spreadsheet_has_headers_for_messages(self):
        spreadsheet = generate_msisdn_message_report.populate_spreadsheet(
            {}, 2)

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
            {"+2340000000": {
                "reg_date": datetime(2017, 01, 01, 00, 00, 00),
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
            {"+2340000000": {
                "id": "54cc71b7-533f-4a83-93c1-e02340000000",
                "reg_date": datetime(2017, 01, 01, 00, 00, 00),
                "facility": "Somewhere",
                "preg_week": 16,
                "msg_type": "text"
            }}, 0)

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['B2'].value,
            datetime(2017, 01, 01, 00, 00, 00))
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
            {"+2340000000": {
                "id": "54cc71b7-533f-4a83-93c1-e02340000000",
                "messages": [{
                    "content": "Test message",
                    "date_sent": datetime(2017, 01, 01, 00, 00, 00),
                    "status": "Delivered"
                }, {
                    "content": "Another test message",
                    "date_sent": datetime(2017, 01, 02, 00, 00, 00),
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
            spreadsheet._workbook.active['G2'].value,
            datetime(2017, 01, 01, 00, 00, 00))
        self.assertEqual(
            spreadsheet._workbook.active['H2'].value, 'Delivered')
        self.assertEqual(
            spreadsheet._workbook.active['I2'].value, 'Another test message')
        self.assertEqual(
            spreadsheet._workbook.active['J2'].value,
            datetime(2017, 01, 02, 00, 00, 00))
        self.assertEqual(
            spreadsheet._workbook.active['K2'].value, 'Undelivered')
