from django.conf import settings
from os.path import getsize
from registrations.models import Registration
from reports.models import ReportTaskStatus
from reports.tasks.base import BaseTask
from reports.utils import ExportWorkbook, generate_random_filename
from seed_services_client import IdentityStoreApiClient


class GenerateMSISDNMessageReport(BaseTask):
    """
    Generate an Excel spreadsheet for a Pathfinder <http://www.pathfinder.org/>
    cohort study which includes details of messages sent to the specified
    MSISDNs.
    """

    def run(self, start_date, end_date, task_status_id, msisdns=[]):
        task_status = ReportTaskStatus.objects.get(id=task_status_id)
        task_status.status = ReportTaskStatus.RUNNING
        task_status.save()

        self.is_client = IdentityStoreApiClient(
            settings.IDENTITY_STORE_TOKEN,
            settings.IDENTITY_STORE_URL,
        )

        data = self.retrieve_identity_info(msisdns)

        data = self.retrieve_registration_info(data)

        spreadsheet = self.populate_spreadsheet(data)

        output_file = generate_random_filename()
        spreadsheet.save(output_file)

        task_status.status = ReportTaskStatus.SENDING
        task_status.file_size = getsize(output_file)
        task_status.save()

        # TODO: Use SendEmail task to send the email

    def retrieve_identity_info(self, msisdns):
        logger = self.get_logger()

        data = {}
        for msisdn in msisdns:
            response = self.is_client.get_identity_by_address('msisdn', msisdn)
            results = list(response['results'])

            if len(results) < 1:
                logger.info(
                    'No results from identity store for {0}'.format(msisdn))
                data[msisdn] = {}
                continue

            if len(results) > 1:
                logger.info(
                    'Multiple results from identity store for {0}'
                    .format(msisdn))
                data[msisdn] = {}
                continue

            data[msisdn] = {'id': results[0]['id'],
                            'created_at': results[0]['created_at']}

        return data

    def retrieve_registration_info(self, data):
        logger = self.get_logger()

        for msisdn in data:
            if data[msisdn].get('id', None) is None:
                # Skip if we didn't find an identity
                continue

            registration = Registration.objects.filter(
                    mother_id=data[msisdn]['id']
                ).order_by('-created_at').first()

            data[msisdn]['reg_date'] = registration.created_at
            data[msisdn]['msg_type'] = registration.data.get('msg_type', "")
            data[msisdn]['preg_week'] = registration.data.get('preg_week', "")

            # Get facility info from the operator's identity
            operator_id = registration.data.get('operator_id', None)
            if operator_id is not None:
                operator_identity = self.is_client.get_identity(operator_id)
                data[msisdn]['facility'] = operator_identity.get(
                        'details', {}).get('facility_name', "")
            else:
                logger.info(
                    'No operator_id on registration for {0}'.format(msisdn))
                data[msisdn]['facility'] = ""

        return data

    def populate_spreadsheet(self, data, list_length):
        workbook = ExportWorkbook()
        sheet = workbook.add_sheet('Data for study cohort', 0)

        sheet.set_header([
            'Phone number',
            'Date registered',
            'Facility',
            'Pregnancy week',
            'Message type',
            'Message 1: content',
            'Message 1: date sent',
            'Message 1: status'
        ])

        for msisdn in data:
            sheet.add_row({
                'Phone number': msisdn,
                'Date registered': data[msisdn]['reg_date'],
                'Facility': data[msisdn]['facility'],
                'Pregnancy week': data[msisdn]['preg_week'],
                'Message type': data[msisdn]['msg_type']
            })

        return workbook


generate_msisdn_message_report = GenerateMSISDNMessageReport()
