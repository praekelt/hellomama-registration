import responses

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

    def test_create_spreadsheet_returns_spreadsheet(self):
        spreadsheet = generate_msisdn_message_report.create_spreadsheet([])
        self.assertTrue(isinstance(spreadsheet, ExportWorkbook))

    @responses.activate
    def test_create_spreadsheet_includes_details(self):
        self.add_response_identity_store_search([{'created_at': '2017-01-01'}])

        spreadsheet = generate_msisdn_message_report.create_spreadsheet(
            ['+2340000000'],
        )

        self.assertEqual(
            spreadsheet._workbook.active['A2'].value, '+2340000000')
        self.assertEqual(
            spreadsheet._workbook.active['B2'].value, '2017-01-01')

    @responses.activate
    def test_create_spreadsheet_discards_msisdn_no_results(self):
        self.add_response_identity_store_search([])

        spreadsheet = generate_msisdn_message_report.create_spreadsheet(
            ['+2340000000'],
        )

        self.assertEqual(spreadsheet._workbook.active['A2'].value, None)

    @responses.activate
    def test_create_spreadsheet_discards_msisdn_multiple_results(self):
        self.add_response_identity_store_search(
            [{'details': '1'}, {'details': '2'}]
        )

        spreadsheet = generate_msisdn_message_report.create_spreadsheet(
            ['+2340000000'],
        )

        self.assertEqual(spreadsheet._workbook.active['A2'].value, None)
