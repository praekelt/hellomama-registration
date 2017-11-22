from datetime import datetime
from django.conf import settings
from os.path import getsize
from registrations.models import Registration
from reports.models import ReportTaskStatus
from reports.tasks.base import BaseTask
from reports.tasks.send_email import SendEmail
from reports.utils import ExportWorkbook, generate_random_filename
from seed_services_client import IdentityStoreApiClient, MessageSenderApiClient


class GenerateMSISDNMessageReport(BaseTask):
    """
    Generate an Excel spreadsheet for a Pathfinder <http://www.pathfinder.org/>
    cohort study which includes details of messages sent to the specified
    MSISDNs.
    """

    def run(self, start_date, end_date, task_status_id, msisdns=[],
            email_recipients=[], email_sender=settings.DEFAULT_FROM_EMAIL,
            email_subject='Seed Control Interface Generated Report', **kwargs):
        task_status = ReportTaskStatus.objects.get(id=task_status_id)
        task_status.status = ReportTaskStatus.RUNNING
        task_status.save()

        is_client = IdentityStoreApiClient(
            settings.IDENTITY_STORE_TOKEN,
            settings.IDENTITY_STORE_URL,
        )
        ms_client = MessageSenderApiClient(
            settings.MESSAGE_SENDER_TOKEN,
            settings.MESSAGE_SENDER_URL,
        )

        data = self.retrieve_identity_info(is_client, msisdns)

        data = self.retrieve_registration_info(is_client, data)

        (data, list_length) = self.retrieve_messages(ms_client, data,
                                                     start_date, end_date)

        spreadsheet = self.populate_spreadsheet(msisdns, data, list_length)

        output_file = generate_random_filename()
        spreadsheet.save(output_file)

        task_status.status = ReportTaskStatus.SENDING
        task_status.file_size = getsize(output_file)
        task_status.save()

        if email_recipients:
            file_name = 'msisdn-report-%s-to-%s.xlsx' % (
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'))
            SendEmail.apply_async(kwargs={
                'subject': email_subject,
                'file_name': file_name,
                'file_location': output_file,
                'sender': email_sender,
                'recipients': email_recipients,
                'task_status_id': task_status_id})

    def retrieve_identity_info(self, is_client, msisdns):
        logger = self.get_logger()

        data = {}
        for msisdn in msisdns:
            response = is_client.get_identity_by_address('msisdn', msisdn)
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

    def retrieve_registration_info(self, is_client, data):
        logger = self.get_logger()

        for msisdn in data:
            if data[msisdn].get('id', None) is None:
                # Skip if we didn't find an identity
                continue

            # Currently we'll only be working with mother msisdns
            registration = Registration.objects.filter(
                    mother_id=data[msisdn]['id']
                ).order_by('-created_at').first()

            if registration is None:
                logger.info(
                    'No registration found with mother_id {0} ({1})'
                    .format(data[msisdn]['id'], msisdn))
                continue

            data[msisdn]['reg_date'] = registration.created_at
            data[msisdn]['msg_type'] = registration.data.get('msg_type', "")
            data[msisdn]['preg_week'] = registration.data.get('preg_week', "")

            # Get facility info from the operator's identity
            operator_id = registration.data.get('operator_id', None)
            if operator_id is not None:
                operator_identity = is_client.get_identity(operator_id)
                data[msisdn]['facility'] = operator_identity.get(
                        'details', {}).get('facility_name', "")
            else:
                logger.info(
                    'No operator_id on registration for {0}'.format(msisdn))
                data[msisdn]['facility'] = ""

        return data

    def retrieve_messages(self, ms_client, data, start_date, end_date):
        logger = self.get_logger()

        longest_list = 0
        for msisdn in data:
            message_list = []

            if data[msisdn].get('id', None) is None:
                # Skip if we didn't find an identity
                continue

            response = ms_client.get_outbounds({
                "to_identity": data[msisdn]['id'],
                "after": start_date.strftime("%Y-%m-%dT00:00:00"),
                "before": end_date.strftime("%Y-%m-%dT00:00:00")
            })
            results = list(response['results'])

            if len(results) < 1:
                logger.info(
                    'No results from message sender for {0}'.format(msisdn))

                data[msisdn]["messages"] = message_list
                continue

            for message in results:
                message_list.append({
                    "content": message['content'],
                    "date_sent": datetime.strptime(message['created_at'],
                                                   "%Y-%m-%dT%H:%M:%S.%fZ"),
                    "status": 'Delivered' if message['delivered'] else 'Undelivered'  # noqa
                })

            data[msisdn]["messages"] = message_list
            if len(message_list) > longest_list:
                longest_list = len(message_list)

        return (data, longest_list)

    def populate_spreadsheet(self, msisdns, data, list_length):
        workbook = ExportWorkbook()
        sheet = workbook.add_sheet('Data for study cohort', 0)

        header = [
            'Phone number',
            'Date registered',
            'Facility',
            'Pregnancy week',
            'Message type'
        ]

        i = 1
        while i <= list_length:
            header.extend([
                'Message %d: content' % i,
                'Message %d: date sent' % i,
                'Message %d: status' % i
            ])
            i += 1

        sheet.set_header(header)

        for msisdn in msisdns:
            if data[msisdn].get('id', None) is None:
                sheet.add_row({'Phone number': msisdn})
                # Skip if there isn't an identity
                continue

            row = {
                'Phone number': msisdn,
                'Date registered': data[msisdn].get('reg_date', ''),
                'Facility': data[msisdn].get('facility', ''),
                'Pregnancy week': data[msisdn].get('preg_week', ''),
                'Message type': data[msisdn].get('msg_type', '')
            }
            j = 1
            for message in data[msisdn].get('messages', []):
                row['Message %d: content' % j] = message['content']
                row['Message %d: date sent' % j] = message['date_sent']
                row['Message %d: status' % j] = message['status']
                j += 1

            sheet.add_row(row)

        return workbook


generate_msisdn_message_report = GenerateMSISDNMessageReport()
